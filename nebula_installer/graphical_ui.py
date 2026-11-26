"""Qt 6 graphical installation wizard for an already mounted LPM Linux target.

The GUI intentionally never runs as root: polkit authorizes a small CLI worker
only after the user has reviewed the plan and typed the exact target path.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from PySide6.QtCore import Qt, QProcess
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget,
)

from .graphical_backend import PlanError, make_config, validate_plan


STEPS = ("Welcome", "Storage", "Packages", "Identity", "Review", "Install")


class NebulaWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LPM Linux • Nebula Installer")
        self.resize(1020, 730)
        self.setMinimumSize(830, 620)
        self.page_index = 0
        self.prepared = None
        self.process: QProcess | None = None
        self.finished = False
        self._pages: list[QWidget] = []
        self._step_labels: list[QLabel] = []
        self._setup_ui()
        self._set_page(0)

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget#central { background: #101525; color: #e6edf9; }
            QWidget#sidebar { background: #171e33; border-right: 1px solid #3c4b69; }
            QLabel#hero { color: #ffffff; font-size: 32px; font-weight: 700; }
            QLabel#subtitle { color: #94a9cd; font-size: 13px; }
            QLabel#pageTitle { color: #f5f7ff; font-size: 25px; font-weight: 700; }
            QLabel#sectionHint { color: #b3c2db; font-size: 13px; }
            QLabel#stepActive { color: #85e6ff; font-weight: 700; font-size: 15px; }
            QLabel#stepInactive { color: #8898b6; font-size: 15px; }
            QLineEdit, QPlainTextEdit, QComboBox {
                background: #242f4a; color: #f0f5ff; border: 1px solid #4c6084;
                padding: 10px; border-radius: 9px; selection-background-color: #376b91;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border: 1px solid #7ad9f7; }
            QPushButton {
                background: #344766; color: #eaf4ff; border: 1px solid #5b7398;
                border-radius: 10px; padding: 11px 19px; font-weight: 600;
            }
            QPushButton:hover { background: #425e82; }
            QPushButton:disabled { background: #273148; color: #73829a; }
            QPushButton#primary { background: #238bb5; color: white; border-color: #65d2f0; }
            QPushButton#primary:hover { background: #2eadd5; }
            QCheckBox { color: #dee8f8; spacing: 9px; }
            QProgressBar { border: 1px solid #526787; border-radius: 8px;
                           background: #232e48; text-align: center; height: 18px; }
            QProgressBar::chunk { background: #60b9d4; border-radius: 7px; }
        """)
        central = QWidget(objectName="central")
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        side = QWidget(objectName="sidebar")
        side.setFixedWidth(260)
        sidebar = QVBoxLayout(side)
        sidebar.setContentsMargins(25, 42, 20, 28)
        sidebar.setSpacing(17)
        logo = QLabel("◈")
        logo.setStyleSheet("color: #85e6ff; font-size: 48px;")
        sidebar.addWidget(logo)
        sidebar.addWidget(QLabel("NEBULA", objectName="hero"))
        subtitle = QLabel("LPM Linux Installer", objectName="subtitle")
        sidebar.addWidget(subtitle)
        sidebar.addSpacing(42)
        for n, name in enumerate(STEPS):
            label = QLabel(f"{n+1:02d}   {name}")
            self._step_labels.append(label)
            sidebar.addWidget(label)
        sidebar.addStretch()
        note = QLabel("LPM • KDE Plasma 6\nNo automatic disk formatting")
        note.setObjectName("subtitle")
        note.setWordWrap(True)
        sidebar.addWidget(note)
        outer.addWidget(side)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(35, 35, 35, 28)
        right_layout.setSpacing(17)
        self.heading = QLabel("", objectName="pageTitle")
        right_layout.addWidget(self.heading)
        self.stack = QStackedWidget()
        right_layout.addWidget(self.stack, stretch=1)
        for builder in (self._welcome, self._storage, self._packages,
                        self._identity, self._review, self._progress):
            page = builder()
            self._pages.append(page)
            self.stack.addWidget(page)
        footer = QHBoxLayout()
        self.back = QPushButton("Back")
        self.back.clicked.connect(self._go_back)
        footer.addWidget(self.back)
        footer.addStretch()
        self.next = QPushButton("Continue")
        self.next.setObjectName("primary")
        self.next.clicked.connect(self._go_next)
        footer.addWidget(self.next)
        right_layout.addLayout(footer)
        outer.addWidget(right, stretch=1)

    def _make_page(self, title: str, hint: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        text = QLabel(title)
        text.setStyleSheet("font-weight: 700; font-size: 18px; color: #f0d5a5;")
        layout.addWidget(text)
        hint_label = QLabel(hint, objectName="sectionHint")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
        return page, layout

    def _welcome(self) -> QWidget:
        page, layout = self._make_page(
            "Install the system, your way",
            "Choose signed repository binaries or build packages from source with LPM. "
            "This edition installs into filesystems you have already mounted.",
        )
        intro = QLabel(
            "REPOSITORY INSTALL\n"
            "Fast installation using lpm install --root TARGET.\n\n"
            "SOURCE INSTALL\n"
            "Compile inside the target chroot using lpm buildpkg --yes.\n\n"
            "SAFETY FIRST\n"
            "Nebula will not partition, format, erase, select a bootloader or reboot "
            "your disk automatically. Verify boot setup before your first reboot."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("background: #1c2943; color: #dbe7f7;"
                            "border: 1px solid #425b80; border-radius: 14px; padding: 24px;")
        layout.addWidget(intro)
        layout.addStretch()
        return page

    def _storage(self) -> QWidget:
        page, layout = self._make_page(
            "Mounted destination",
            "Prepare and mount your partitions from the live session first. "
            "The destination must be a mountpoint, never /, and /dev, /proc and /sys "
            "must be mounted below it.",
        )
        form = QFormLayout()
        form.setVerticalSpacing(15)
        self.target = QLineEdit("/mnt/lpm")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_target)
        target_row = QWidget()
        target_layout = QHBoxLayout(target_row)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.addWidget(self.target)
        target_layout.addWidget(browse)
        form.addRow("Target root:", target_row)
        self.root_dev = QLineEdit()
        self.root_dev.setPlaceholderText("/dev/nvme0n1p2 or UUID=...")
        self.root_fs = QComboBox()
        self.root_fs.setEditable(True)
        self.root_fs.addItems(["ext4", "btrfs", "xfs", "f2fs"])
        form.addRow("Root partition:", self.root_dev)
        form.addRow("Filesystem:", self.root_fs)
        layout.addLayout(form)
        probe = QPushButton("Detect mounted root filesystem")
        probe.clicked.connect(self._detect_mount)
        layout.addWidget(probe)
        layout.addWidget(QLabel("Additional fstab entries — DEVICE | MOUNTPOINT | FSTYPE | OPTIONS"))
        self.extras = QPlainTextEdit()
        self.extras.setPlaceholderText("/dev/nvme0n1p1 | /boot | vfat | umask=0077\n"
                                       "/dev/nvme0n1p3 | /home | ext4 | defaults")
        self.extras.setMaximumHeight(120)
        layout.addWidget(self.extras)
        layout.addStretch()
        return page

    def _packages(self) -> QWidget:
        page, layout = self._make_page(
            "Package installation",
            "Bootstrap packages, if specified, always come from the repository. "
            "In source mode, the remaining packages build within the target chroot.",
        )
        form = QFormLayout()
        form.setVerticalSpacing(17)
        self.mode = QComboBox()
        self.mode.addItem("Repository binaries — lpm install", "repository")
        self.mode.addItem("Build from source — lpm buildpkg", "source")
        form.addRow("Install mode:", self.mode)
        self.bootstrap = QPlainTextEdit()
        self.bootstrap.setPlaceholderText("Optional: lpm-filesystem, lpm, linux, systemd")
        self.bootstrap.setMaximumHeight(94)
        form.addRow("Base/bootstrap packages:", self.bootstrap)
        self.packages = QPlainTextEdit("plasma6-full")
        self.packages.setMaximumHeight(110)
        form.addRow("System/desktop packages:", self.packages)
        layout.addLayout(form)
        tip = QLabel("Use comma/space-separated LPM package names. "
                     "Source mode requires LPM, compilers and dependencies available "
                     "inside your target chroot. It may take substantially longer.")
        tip.setObjectName("sectionHint")
        tip.setWordWrap(True)
        layout.addWidget(tip)
        layout.addStretch()
        return page

    def _identity(self) -> QWidget:
        page, layout = self._make_page(
            "Identity and locale",
            "Your password is converted to a SHA-512 crypt hash locally and sent "
            "only to the privileged installer. It is never saved in a config file.",
        )
        form = QFormLayout()
        form.setVerticalSpacing(15)
        self.hostname = QLineEdit("lpm-linux")
        self.timezone = QLineEdit("America/Detroit")
        self.locale = QLineEdit("en_US.UTF-8")
        self.username = QLineEdit()
        self.username.setPlaceholderText("Your login name")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password2 = QLineEdit()
        self.password2.setEchoMode(QLineEdit.EchoMode.Password)
        for label, widget in (
            ("Hostname:", self.hostname), ("Timezone:", self.timezone),
            ("Locale:", self.locale), ("Username:", self.username),
            ("Password:", self.password), ("Confirm password:", self.password2),
        ):
            form.addRow(label, widget)
        layout.addLayout(form)
        layout.addStretch()
        return page

    def _review(self) -> QWidget:
        page, layout = self._make_page(
            "Review your installation",
            "Confirm every entry, check the mounted disks and keep a backup. "
            "Package installation changes the destination system, but there is "
            "no automatic formatting or bootloader installation.",
        )
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        layout.addWidget(self.summary, stretch=1)
        self.ack = QCheckBox(
            "I verified the target mount, have a backup, and understand package "
            "installation modifies the target."
        )
        layout.addWidget(self.ack)
        return page

    def _progress(self) -> QWidget:
        page, layout = self._make_page(
            "Installing LPM Linux",
            "Live command output from the privileged LPM worker. "
            "Do not power off or unmount the target while packages are installing.",
        )
        self.activity = QProgressBar()
        self.activity.setRange(0, 0)
        layout.addWidget(self.activity)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.document().setMaximumBlockCount(6000)
        layout.addWidget(self.log, stretch=1)
        return page

    def _set_page(self, index: int) -> None:
        self.page_index = index
        self.stack.setCurrentIndex(index)
        self.heading.setText(STEPS[index])
        for i, label in enumerate(self._step_labels):
            label.setObjectName("stepActive" if i == index else "stepInactive")
            label.style().unpolish(label)
            label.style().polish(label)
        self.back.setEnabled(index > 0 and index < 5)
        self.next.setText(
            "Close" if self.finished else
            ("Install to target" if index == 4 else "Continue")
        )
        self.next.setEnabled(index != 5 or self.finished)

    def _browse_target(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select mounted target root",
                                                self.target.text())
        if path:
            self.target.setText(path)

    def _detect_mount(self) -> None:
        target = str(Path(self.target.text().strip()).expanduser().resolve())
        try:
            result = subprocess.run(
                ["findmnt", "-rn", "-M", target, "-o", "SOURCE,FSTYPE"],
                check=True, capture_output=True, text=True, timeout=8,
            )
            fields = result.stdout.strip().split()
            if len(fields) != 2:
                raise ValueError("Unable to parse mount details")
            self.root_dev.setText(fields[0])
            self.root_fs.setCurrentText(fields[1])
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            QMessageBox.warning(self, "Mount detection", f"Mount {target} first.\n{exc}")

    def _go_back(self) -> None:
        if 0 < self.page_index < 5:
            self._set_page(self.page_index - 1)

    def _build_plan(self):
        if self.password.text() != self.password2.text():
            raise PlanError("Passwords do not match")
        plan = make_config(
            target_root=self.target.text(),
            root_device=self.root_dev.text(),
            root_fs=self.root_fs.currentText(),
            extra_partitions=self.extras.toPlainText(),
            hostname=self.hostname.text(),
            timezone=self.timezone.text(),
            locale=self.locale.text(),
            username=self.username.text(),
            password=self.password.text(),
            install_mode=self.mode.currentData(),
            bootstrap_text=self.bootstrap.toPlainText(),
            packages_text=self.packages.toPlainText(),
        )
        validate_plan(plan)
        return plan

    def _show_review(self) -> bool:
        try:
            self.prepared = self._build_plan()
        except (PlanError, OSError) as exc:
            QMessageBox.warning(self, "Installation plan needs attention", str(exc))
            return False
        cfg = self.prepared
        lines = [
            f"TARGET ROOT         {cfg.target_root}",
            f"MODE                {cfg.install_mode.upper()}",
            f"HOSTNAME            {cfg.hostname}",
            f"TIMEZONE            {cfg.timezone}",
            f"LOCALE              {cfg.locale}",
            f"PRIMARY USER        {cfg.user.username}",
            "",
            "BOOTSTRAP (REPOSITORY)",
            "  " + (", ".join(cfg.bootstrap_packages) or "(already prepared)"),
            "",
            "SYSTEM PACKAGES",
            "  " + ", ".join(cfg.packages),
            "",
            "FSTAB ENTRIES",
        ]
        for part in cfg.partitions:
            lines.append(f"  {part.device}  ->  {part.mountpoint}  ({part.filesystem}; {part.options})")
        lines += ["", "NO repartition, mkfs, GRUB setup, or automatic reboot will occur.",
                  "Configure the bootloader separately after installation."]
        self.summary.setPlainText("\n".join(lines))
        self.ack.setChecked(False)
        return True

    def _go_next(self) -> None:
        if self.finished:
            self.close()
            return
        if self.page_index == 3 and not self._show_review():
            return
        if self.page_index == 4:
            self._start_install()
            return
        if self.page_index < 4:
            self._set_page(self.page_index + 1)

    def _start_install(self) -> None:
        if not self.ack.isChecked():
            QMessageBox.warning(self, "Review required", "Check the review acknowledgement.")
            return
        try:
            validate_plan(self.prepared)
        except (PlanError, OSError) as exc:
            QMessageBox.warning(self, "Destination changed", str(exc))
            return
        destination = str(self.prepared.target_root)
        typed, accepted = QInputDialog.getText(
            self, "Final installation confirmation",
            f"Type the exact mounted destination to proceed:\n{destination}",
        )
        if not accepted or typed.strip() != destination:
            return
        if os.geteuid() != 0 and not shutil.which("pkexec"):
            QMessageBox.critical(
                self, "Authorization unavailable",
                "Install polkit/pkexec with a desktop authentication agent. "
                "The GUI must authorize its privileged worker before installation.",
            )
            return
        self._set_page(5)
        self.password.clear()
        self.password2.clear()
        self.log.setPlainText("Starting authorized installation…\n")
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._worker_finished)
        args = ["-u", "-m", "nebula_installer", "--apply-stdin",
                "--confirm-target", destination]
        cmd = sys.executable
        if os.geteuid() != 0:
            args = [cmd, *args]
            cmd = shutil.which("pkexec")
        self.process.start(cmd, args)
        if not self.process.waitForStarted(6000):
            self.log.appendPlainText("Failed to launch installer: " + self.process.errorString())
            self._end_install(False)
            return
        self.process.write(json.dumps(self.prepared.to_dict()).encode("utf-8"))
        self.process.closeWriteChannel()
        self.prepared = None

    def _read_stdout(self) -> None:
        if self.process is not None:
            data = bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
            if data:
                self.log.insertPlainText(data)
                self.log.ensureCursorVisible()

    def _read_stderr(self) -> None:
        if self.process is not None:
            data = bytes(self.process.readAllStandardError()).decode("utf-8", "replace")
            if data:
                self.log.insertPlainText(data)
                self.log.ensureCursorVisible()

    def _worker_finished(self, code: int, status) -> None:
        self._read_stdout()
        self._read_stderr()
        success = code == 0 and status == QProcess.ExitStatus.NormalExit
        self.log.appendPlainText(
            "\nCompleted. Verify fstab and install/configure your bootloader before reboot."
            if success else f"\nInstallation stopped (exit code {code}); inspect the log."
        )
        self._end_install(success)

    def _end_install(self, success: bool) -> None:
        self.finished = True
        self.activity.setRange(0, 1)
        self.activity.setValue(1 if success else 0)
        self._set_page(5)

    def closeEvent(self, event) -> None:
        if self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.warning(
                self, "Installation running",
                "Wait for LPM to finish; interrupting a package transaction "
                "could leave the target inconsistent.",
            )
            event.ignore()
            return
        event.accept()


def run_graphical() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Nebula Installer")
    window = NebulaWindow()
    window.show()
    return app.exec()
