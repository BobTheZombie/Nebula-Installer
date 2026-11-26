"""Safety-gated execution layer shared by the Qt wizard and privileged worker.

This stage installs into *pre-mounted* partitions. Disk partitioning,
filesystem formatting and bootloader installation are deliberately not
performed by the GUI. A real block-device confirmation screen is required
before those operations are added.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from .config import InstallConfig, Partition, User
from .installer import Installer


class PlanError(ValueError):
    """The plan is invalid or cannot safely be executed."""


PACKAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+:-]{0,127}$")
DEVICE = re.compile(r"^(?:/dev/[A-Za-z0-9_./+-]+|UUID=[A-Fa-f0-9-]+|PARTUUID=[A-Fa-f0-9-]+|LABEL=[A-Za-z0-9_.-]+)$")
FSTYPE = re.compile(r"^[A-Za-z0-9_+-]+$")
OPTIONS = re.compile(r"^[A-Za-z0-9_,=./:-]+$")

HOSTNAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}$")
USERNAME = re.compile(r"^[a-z_][a-z0-9_-]{0,30}$")
LOCALE = re.compile(r"^[A-Za-z0-9_.@-]{1,90}$")


def package_names(value: str) -> tuple[str, ...]:
    names = tuple(dict.fromkeys(
        item.strip() for item in re.split(r"[,\s]+", value) if item.strip()
    ))
    for name in names:
        if not PACKAGE.fullmatch(name):
            raise PlanError(f"Invalid package name: {name!r}")
    return names


def partition_rows(root_device: str, root_fs: str, extras: str) -> tuple[Partition, ...]:
    root_device, root_fs = root_device.strip(), root_fs.strip()
    if not DEVICE.fullmatch(root_device) or not FSTYPE.fullmatch(root_fs):
        raise PlanError("Root device must be a /dev path, UUID, PARTUUID or LABEL and have a filesystem")
    rows = [Partition(device=root_device, mountpoint="/", filesystem=root_fs, passno=1)]
    seen = {"/"}
    for lineno, line in enumerate(extras.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        bits = [piece.strip() for piece in line.split("|")]
        if len(bits) not in (3, 4):
            raise PlanError(f"Partition line {lineno}: expected DEVICE | MOUNTPOINT | FSTYPE | OPTIONS")
        dev, mount, fs = bits[:3]
        opt = bits[3] if len(bits) == 4 else "defaults"
        if (not DEVICE.fullmatch(dev) or not mount.startswith("/") or
                mount != str(Path(mount)) or
                ".." in Path(mount).parts or any(ch.isspace() for ch in mount) or
                not FSTYPE.fullmatch(fs) or not OPTIONS.fullmatch(opt) or
                mount in seen):
            raise PlanError(f"Invalid or duplicate partition entry on line {lineno}")
        seen.add(mount)
        rows.append(Partition(dev, mount, fs, opt, passno=0 if fs in ("vfat", "swap") else 2))
    return tuple(rows)


def hash_password(password: str) -> str:
    """Generate an /etc/shadow-compatible hash without revealing the password in argv."""
    if not password or len(password) < 8:
        raise PlanError("Choose a user password with at least eight characters")
    if "\x00" in password or "\n" in password or ":" in password:
        raise PlanError("Password must not contain null, newline, or colon")
    try:
        result = subprocess.run(
            ["openssl", "passwd", "-6", "-stdin"],
            input=password + "\n", text=True, capture_output=True,
            timeout=20, check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PlanError("Cannot generate password hash: OpenSSL is required") from exc
    value = result.stdout.strip()
    if not value.startswith("$6$"):
        raise PlanError("OpenSSL did not return a SHA-512 crypt password hash")
    return value


def make_config(*, target_root: str, root_device: str, root_fs: str,
                extra_partitions: str, hostname: str, timezone: str,
                locale: str, username: str, password: str,
                install_mode: str, bootstrap_text: str,
                packages_text: str) -> InstallConfig:
    return InstallConfig(
        target_root=Path(target_root).expanduser().resolve(),
        hostname=hostname.strip(), timezone=timezone.strip(), locale=locale.strip(),
        bootstrap_packages=package_names(bootstrap_text),
        packages=package_names(packages_text),
        partitions=partition_rows(root_device, root_fs, extra_partitions),
        user=User(username=username.strip(), password=hash_password(password),
                  groups=("wheel",), shell="/bin/bash"),
        install_mode=install_mode,
        register_grub_hook=False,
        sync_fstab_mounts=False,
    )


def validate_plan(config: InstallConfig, *, confirmed_target: Path | None = None,
                  check_environment: bool = True) -> None:
    """Reject host-target confusion, unsupported modes and incomplete system setup."""
    target = config.target_root
    if target == Path("/") or not target.is_absolute():
        raise PlanError("Refusing to install into the live system root")
    if confirmed_target is not None and target != confirmed_target.resolve():
        raise PlanError("Confirmed destination differs from the installation plan")
    if config.install_mode not in ("repository", "source"):
        raise PlanError("Select repository or source mode")
    if not HOSTNAME.fullmatch(config.hostname) or ".." in config.hostname:
        raise PlanError("Invalid hostname")
    if not USERNAME.fullmatch(config.user.username):
        raise PlanError("Invalid username")
    if not LOCALE.fullmatch(config.locale):
        raise PlanError("Invalid locale")
    zone = Path(config.timezone)
    if not config.timezone or zone.is_absolute() or ".." in zone.parts:
        raise PlanError("Invalid timezone")
    if not config.user.password.startswith("$6$"):
        raise PlanError("Expected a SHA-512 crypt password hash")
    for name in (*config.bootstrap_packages, *config.packages):
        if not PACKAGE.fullmatch(name):
            raise PlanError(f"Invalid package: {name!r}")
    if not config.bootstrap_packages and not config.packages:
        raise PlanError("Select at least one package to install")
    if not config.partitions or len([p for p in config.partitions if p.mountpoint == "/"]) != 1:
        raise PlanError("Define exactly one root filesystem in fstab")
    if config.register_grub_hook or config.sync_fstab_mounts:
        raise PlanError("Graphical installer does not enable legacy GRUB hooks or mount synchronization")
    for part in config.partitions:
        if (not DEVICE.fullmatch(part.device) or
                not FSTYPE.fullmatch(part.filesystem) or
                not OPTIONS.fullmatch(part.options) or
                not part.mountpoint.startswith("/") or
                part.mountpoint != str(Path(part.mountpoint)) or
                ".." in Path(part.mountpoint).parts or
                any(ch.isspace() for ch in part.mountpoint)):
            raise PlanError("Invalid fstab partition data")
    if check_environment:
        if not target.exists() or not target.is_dir() or not os.path.ismount(target):
            raise PlanError(f"Target {target} must be an existing, explicitly mounted filesystem")
        for name in ("dev", "proc", "sys"):
            if not os.path.ismount(target / name):
                raise PlanError(f"Bind/mount {target / name} before installing (see README)")
        for part in config.partitions:
            if (part.mountpoint != "/" and part.filesystem != "swap" and
                    not os.path.ismount(target / part.mountpoint.lstrip("/"))):
                raise PlanError(f"Mount the selected {part.mountpoint} partition before installing")
        if (config.install_mode == "repository" or config.bootstrap_packages) and not shutil.which("lpm"):
            raise PlanError("Host lpm executable not available")
        if config.install_mode == "source" and not config.bootstrap_packages:
            if not any((target / p).is_file() for p in ("usr/bin/lpm", "usr/local/bin/lpm", "bin/lpm")):
                raise PlanError("Source install needs an initialized chroot containing lpm")


def apply_stdin(confirmed_target: Path | None) -> None:
    """Privileged worker entry point: read a bounded, hashed-only plan from stdin."""
    if confirmed_target is None:
        raise SystemExit("Missing --confirm-target")
    if os.geteuid() != 0:
        raise SystemExit("Root privileges required (use the graphical authorization prompt)")
    try:
        raw = sys.stdin.buffer.read(131073)
        if len(raw) > 131072:
            raise PlanError("Installation plan too large")
        config = InstallConfig.from_dict(json.loads(raw.decode("utf-8")))
        validate_plan(config, confirmed_target=confirmed_target)
    except (UnicodeError, ValueError, KeyError, TypeError, PlanError) as exc:
        raise SystemExit(f"Invalid installation plan: {exc}") from exc
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout,
                        force=True)
    os.environ["NEBULA_STREAM_COMMANDS"] = "1"
    print(f"Confirmed destination: {config.target_root}", flush=True)
    print(f"Installing in {config.install_mode} mode; existing filesystems will be reused.", flush=True)
    # Existing Installer orchestrates LPM, fstab/sysconfig and account creation.
    # No mkfs, partition-table edits, mount changes, or bootloader writes here.
    Installer(config).run()
    print("Installation steps finished. Configure and verify the bootloader before rebooting.", flush=True)
