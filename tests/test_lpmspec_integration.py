"""Tests covering lpmspec handling and integration points."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nebula_installer import lpmspec
from nebula_installer.helpers import lpm
from nebula_installer.helpers.commands import CommandResult


def _write_spec(
    directory: Path,
    *,
    include_install_root: bool = True,
    include_sysconfig: bool = True,
    include_sysconfig_root: bool = True,
) -> Path:
    data = {
        "api_version": "1.0",
        "generated_at": 1_708_000_000,
        "lpm": {
            "name": "Example LPM",
            "version": "1.2.3",
            "build": "build-42",
        },
        "cli": {
            "usage": "usage: lpm [options] <command>",
            "description": "Example specification for testing",
            "arguments": [
                {
                    "name": "sysconfig",
                    "flags": ["--sysconfig"],
                    "help": "Generate system configuration and exit",
                    "positional": False,
                },
                {
                    "name": "sysconfig_root",
                    "flags": ["--sysconfig-root"],
                    "help": "Root path used when generating sysconfig",
                    "positional": False,
                },
            ],
            "commands": [
                {
                    "name": "install",
                    "help": "Install packages",
                    "usage": "lpm install [options] names",
                    "description": "",
                    "arguments": [
                        {
                            "name": "names",
                            "flags": ["names"],
                            "help": "Packages to install",
                            "positional": True,
                            "nargs": "+",
                        },
                        {
                            "name": "root",
                            "flags": ["--root"],
                            "help": "Target root path",
                            "positional": False,
                        },
                    ],
                }
            ],
        },
    }

    if not include_install_root:
        data["cli"]["commands"][0]["arguments"] = [
            item
            for item in data["cli"]["commands"][0]["arguments"]
            if "--root" not in item.get("flags", [])
        ]

    if not include_sysconfig:
        data["cli"]["arguments"] = [
            item for item in data["cli"]["arguments"] if "--sysconfig" not in item.get("flags", [])
        ]

    if not include_sysconfig_root:
        data["cli"]["arguments"] = [
            item
            for item in data["cli"]["arguments"]
            if "--sysconfig-root" not in item.get("flags", [])
        ]

    path = directory / "lpmspec.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _set_spec(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setenv(lpmspec.ENV_LPMSPEC_PATH, str(path))
    lpmspec.clear_cached_lpmspec()


def test_load_lpmspec_parses_install_command(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path)
    loaded = lpmspec.load_lpmspec(spec_path)

    command = loaded.cli.get_command("install")
    assert command is not None
    assert command.find_argument_by_flag("--root") is not None
    assert loaded.lpm_name == "Example LPM"
    assert loaded.lpm_version == "1.2.3"


def test_install_packages_respects_lpmspec(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path)
    _set_spec(monkeypatch, spec_path)

    recorded: dict[str, list[str]] = {}

    def fake_run(command, **kwargs):
        recorded["command"] = list(command)
        return CommandResult(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(lpm.commands, "run", fake_run)

    target_root = tmp_path / "root"
    target_root.mkdir()

    lpm.install_packages(["example"], target_root)
    assert recorded["command"][:3] == ["lpm", "install", "--root"]
    assert "--reinstall" not in recorded["command"]


def test_install_packages_detects_removed_root_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    spec_path = _write_spec(tmp_path, include_install_root=False)
    _set_spec(monkeypatch, spec_path)

    with pytest.raises(RuntimeError):
        lpm.install_packages(["example"], tmp_path / "root")


def test_generate_sysconfig_detects_missing_flags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    spec_path = _write_spec(tmp_path, include_sysconfig_root=False)
    _set_spec(monkeypatch, spec_path)

    with pytest.raises(RuntimeError):
        lpm.generate_sysconfig(
            tmp_path / "root",
            hostname="host",
            timezone="UTC",
            locale="en_US.UTF-8",
        )


def test_wizard_hero_tagline_uses_lpmspec(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path)
    _set_spec(monkeypatch, spec_path)

    pytest.importorskip("textual")
    from nebula_installer.textual_ui import WizardApp

    app = WizardApp()
    tagline = app._hero_tagline()
    assert "Example LPM" in tagline
    assert "lpmspec API 1.0" in tagline
