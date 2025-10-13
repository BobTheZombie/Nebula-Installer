"""Textual-based interface for the Nebula installer wizard."""

from __future__ import annotations

import asyncio
import crypt
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
    TabPane,
    TabbedContent,
    TextArea,
)

from .config import InstallConfig, Partition, User
from .constants import DEFAULT_BOOTSTRAP_PACKAGES
from .lpmspec import get_cached_lpmspec


@dataclass(slots=True)
class _PartitionDialogResult:
    index: int | None
    partition: Partition


class PartitionDialog(ModalScreen[_PartitionDialogResult | None]):
    """Modal dialog that captures data for a single partition entry."""

    CSS = """
    PartitionDialog > Vertical {
        background: $panel;
        border: tall $primary;
        padding: 2 3;
        width: 60ch;
        height: auto;
        margin: auto;
        align: center middle;
    }

    PartitionDialog .dialog-title {
        text-style: bold;
        color: $text;
        padding-bottom: 1;
    }

    PartitionDialog Grid {
        grid-size: 2 3;
        grid-gutter: 1 0;
    }

    PartitionDialog .actions {
        padding-top: 2;
        align-horizontal: right;
        width: 100%;
    }
    """

    def __init__(self, index: int | None = None, partition: Partition | None = None) -> None:
        super().__init__()
        self._index = index
        self._partition = partition

    def compose(self) -> ComposeResult:
        partition = self._partition
        dump_value = str(partition.dump) if partition else "0"
        passno_value = str(partition.passno) if partition else "2"
        with Vertical():
            yield Static(
                "Partition details",
                classes="dialog-title",
            )
            with Grid():
                yield Label("Device", classes="field-label")
                yield Input(
                    partition.device if partition else "",
                    placeholder="/dev/sda1",
                    id="device",
                )
                yield Label("Mountpoint", classes="field-label")
                yield Input(
                    partition.mountpoint if partition else "/",
                    placeholder="/",
                    id="mountpoint",
                )
                yield Label("Filesystem", classes="field-label")
                yield Input(
                    partition.filesystem if partition else "ext4",
                    placeholder="ext4",
                    id="filesystem",
                )
                yield Label("Options", classes="field-label")
                yield Input(
                    partition.options if partition else "defaults",
                    placeholder="defaults",
                    id="options",
                )
                yield Label("Dump", classes="field-label")
                yield Input(
                    dump_value,
                    placeholder="0",
                    id="dump",
                )
                yield Label("Pass", classes="field-label")
                yield Input(
                    passno_value,
                    placeholder="2",
                    id="passno",
                )
            with Horizontal(classes="actions"):
                yield Button("Cancel", id="cancel")
                yield Button("Save", id="save", variant="primary")

    def _gather_values(self) -> Partition:
        device = self.query_one("#device", Input).value.strip()
        mountpoint = self.query_one("#mountpoint", Input).value.strip() or "/"
        filesystem = self.query_one("#filesystem", Input).value.strip() or "ext4"
        options = self.query_one("#options", Input).value.strip() or "defaults"
        dump_value = self.query_one("#dump", Input).value.strip() or "0"
        pass_value = self.query_one("#passno", Input).value.strip() or "2"
        if not device:
            raise ValueError("Device is required")
        try:
            dump_int = int(dump_value)
            pass_int = int(pass_value)
        except ValueError as exc:  # pragma: no cover - validation guard
            raise ValueError("Dump and Pass must be integers") from exc
        return Partition(
            device=device,
            mountpoint=mountpoint,
            filesystem=filesystem,
            options=options,
            dump=dump_int,
            passno=pass_int,
        )

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#save")
    def _save(self) -> None:
        try:
            partition = self._gather_values()
        except ValueError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self.dismiss(_PartitionDialogResult(self._index, partition))


class WizardApp(App[InstallConfig]):
    """Textual application that collects installation data."""

    CSS = """
    Screen {
        background: $surface;
    }

    # Hero header styling
    .hero {
        padding: 2 3;
        background: $boost;
        border: heavy $accent;
        margin: 1 2;
        text-style: bold;
    }

    .hero .tagline {
        color: $text-muted;
        padding-top: 1;
    }

    TabbedContent {
        height: 1fr;
        margin: 0 2 2 2;
    }

    TabPane Container {
        padding: 1 2;
        row-gap: 1;
    }

    TabPane Input, TabPane TextArea {
        width: 100%;
    }

    TabPane TextArea {
        min-height: 6;
    }

    .form-grid {
        grid-size: 2;
        grid-gutter: 1;
    }

    .form-grid Label {
        color: $text-muted;
    }

    .finish-bar {
        margin: 0 2 2 2;
        align: right middle;
    }

    DataTable#partitions {
        height: 12;
        border: tall $primary;
    }

    .partition-actions {
        column-gap: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "finish", "Save and exit"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(
        self,
        base_config: InstallConfig | None = None,
        default_bootstrap: Sequence[str] | None = None,
    ) -> None:
        super().__init__()
        self.base_config = base_config
        self._partitions = list(base_config.partitions) if base_config else []
        self._default_bootstrap = (
            tuple(default_bootstrap) if default_bootstrap else DEFAULT_BOOTSTRAP_PACKAGES
        )
        self._lpmspec = get_cached_lpmspec()

    def _hero_tagline(self) -> str:
        spec = self._lpmspec
        if not spec:
            return "Powered by LPM – the Linux Package Manager"

        details: list[str] = []
        if spec.lpm_version:
            details.append(f"v{spec.lpm_version}")
        if spec.lpm_build:
            details.append(f"build {spec.lpm_build}")
        detail_str = " ".join(details)

        base = f"Powered by {spec.lpm_name}"
        if detail_str:
            base = f"{base} {detail_str}"
        return f"{base} – lpmspec API {spec.api_version}"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(classes="hero"):
            yield Static("Nebula Installer for LuminOS", markup=False)
            yield Static(self._hero_tagline(), classes="tagline")
        with TabbedContent():
            with TabPane("System"):
                with Container():
                    yield Label("Target root directory")
                    yield Input(
                        str(self.base_config.target_root)
                        if self.base_config
                        else "/mnt/luminos",
                        id="target_root",
                    )
                    yield Label("Hostname")
                    yield Input(
                        self.base_config.hostname if self.base_config else "luminos",
                        id="hostname",
                    )
                    yield Label("Timezone")
                    yield Input(
                        self.base_config.timezone if self.base_config else "UTC",
                        id="timezone",
                    )
                    yield Label("Locale")
                    yield Input(
                        self.base_config.locale if self.base_config else "en_US.UTF-8",
                        id="locale",
                    )
            with TabPane("Packages"):
                with Container():
                    bootstrap_default = (
                        ", ".join(self.base_config.bootstrap_packages)
                        if self.base_config
                        else ", ".join(self._default_bootstrap)
                    )
                    yield Label("Bootstrap packages (comma separated)")
                    yield TextArea(bootstrap_default, id="bootstrap_packages")
                    packages_default = (
                        ", ".join(self.base_config.packages)
                        if self.base_config
                        else ""
                    )
                    yield Label("Additional packages (comma separated)")
                    yield TextArea(packages_default, id="packages")
            with TabPane("Storage"):
                with Container():
                    yield Label(
                        "Partitions for /etc/fstab (select a row to edit or remove)",
                        classes="section-label",
                    )
                    table = DataTable(id="partitions")
                    table.add_columns("Device", "Mountpoint", "Filesystem", "Options", "Dump", "Pass")
                    yield table
                    with Horizontal(classes="partition-actions"):
                        yield Button("Add", id="add_partition", variant="primary")
                        yield Button("Edit", id="edit_partition")
                        yield Button("Remove", id="remove_partition", variant="error")
            with TabPane("User"):
                with Container():
                    username_default = (
                        self.base_config.user.username if self.base_config else "lumina"
                    )
                    yield Label("Primary username")
                    yield Input(username_default, id="username")
                    yield Label("Password (leave blank to keep existing)")
                    yield Input(password=True, id="password")
                    yield Label("Confirm password")
                    yield Input(password=True, id="confirm_password")
                    groups_default = ", ".join(self.base_config.user.groups) if self.base_config else "wheel"
                    yield Label("Supplementary groups (comma separated)")
                    yield Input(groups_default, id="groups")
                    shell_default = self.base_config.user.shell if self.base_config else "/bin/bash"
                    yield Label("Login shell")
                    yield Input(shell_default, id="shell")
        with Horizontal(classes="finish-bar"):
            yield Button("Finish", id="finish", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_partitions()

    def _refresh_partitions(self) -> None:
        table = self.query_one(DataTable)
        table.clear(rows=True)
        for index, partition in enumerate(self._partitions):
            table.add_row(
                partition.device,
                partition.mountpoint,
                partition.filesystem,
                partition.options,
                str(partition.dump),
                str(partition.passno),
                key=index,
            )

    def action_finish(self) -> None:
        self._finalize()

    @on(Button.Pressed, "#finish")
    def _click_finish(self) -> None:
        self._finalize()

    def _gather_packages(self, widget_id: str, fallback: Sequence[str]) -> Sequence[str]:
        raw = self.query_one(f"#{widget_id}", TextArea).text
        if not raw.strip():
            return tuple(fallback)
        items = [item.strip() for item in raw.replace("\n", ",").split(",") if item.strip()]
        return tuple(dict.fromkeys(items))

    def _finalize(self) -> None:
        try:
            config = self._build_config()
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        self.exit(config)

    def _build_config(self) -> InstallConfig:
        target_root_text = self.query_one("#target_root", Input).value.strip()
        if not target_root_text:
            raise ValueError("Target root directory is required")
        target_root = Path(target_root_text).expanduser().resolve()
        hostname = self.query_one("#hostname", Input).value.strip() or "luminos"
        timezone = self.query_one("#timezone", Input).value.strip() or "UTC"
        locale = self.query_one("#locale", Input).value.strip() or "en_US.UTF-8"

        bootstrap_packages = self._gather_packages(
            "bootstrap_packages",
            self.base_config.bootstrap_packages if self.base_config else self._default_bootstrap,
        )
        packages = self._gather_packages("packages", self.base_config.packages if self.base_config else [])

        partitions = list(self._partitions)
        if not partitions:
            raise ValueError("At least one partition entry is required")

        username = self.query_one("#username", Input).value.strip() or "lumina"
        password_widget = self.query_one("#password", Input)
        password_value = password_widget.value
        confirm_password = self.query_one("#confirm_password", Input).value
        if password_value:
            if password_value != confirm_password:
                raise ValueError("Passwords do not match")
            hashed_password = crypt.crypt(password_value, crypt.mksalt(crypt.METHOD_SHA512))
        else:
            if self.base_config and self.base_config.user.password:
                hashed_password = self.base_config.user.password
            else:
                raise ValueError("Password is required")
        groups_raw = self.query_one("#groups", Input).value
        groups = tuple(
            dict.fromkeys(
                [value.strip() for value in groups_raw.replace("\n", ",").split(",") if value.strip()]
            )
        )
        if not groups:
            groups = ("wheel",)
        shell = self.query_one("#shell", Input).value.strip() or "/bin/bash"

        return InstallConfig(
            target_root=target_root,
            hostname=hostname,
            timezone=timezone,
            locale=locale,
            bootstrap_packages=bootstrap_packages,
            packages=packages,
            partitions=tuple(partitions),
            user=User(
                username=username,
                password=hashed_password,
                groups=groups,
                shell=shell,
            ),
        )

    def _selected_partition_index(self) -> int | None:
        table = self.query_one(DataTable)
        row_key = table.cursor_row_key
        if row_key is None:
            return None
        if isinstance(row_key, int):
            return row_key
        return None

    async def _open_partition_dialog(
        self, index: int | None = None, partition: Partition | None = None
    ) -> None:
        result = await self.push_screen_wait(PartitionDialog(index=index, partition=partition))
        if not result:
            return
        if result.index is None:
            self._partitions.append(result.partition)
        else:
            self._partitions[result.index] = result.partition
        self._refresh_partitions()

    @on(Button.Pressed, "#add_partition")
    async def _add_partition(self) -> None:
        await self._open_partition_dialog()

    @on(Button.Pressed, "#edit_partition")
    async def _edit_partition(self) -> None:
        index = self._selected_partition_index()
        if index is None:
            self.notify("Select a partition to edit", severity="warning")
            return
        await self._open_partition_dialog(index=index, partition=self._partitions[index])

    @on(Button.Pressed, "#remove_partition")
    def _remove_partition(self) -> None:
        index = self._selected_partition_index()
        if index is None:
            self.notify("Select a partition to remove", severity="warning")
            return
        del self._partitions[index]
        self._refresh_partitions()


def launch_wizard(
    base_config: InstallConfig | None = None,
    default_bootstrap: Sequence[str] | None = None,
) -> InstallConfig:
    """Launch the Textual wizard and return the resulting configuration."""

    app = WizardApp(base_config, default_bootstrap=default_bootstrap)
    return asyncio.run(app.run_async())

