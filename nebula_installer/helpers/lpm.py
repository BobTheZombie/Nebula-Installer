"""Helpers for interacting with ``lpm``."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Mapping, Sequence

from . import commands

LOGGER = logging.getLogger(__name__)


def generate_sysconfig(
    target_root: Path,
    *,
    hostname: str,
    timezone: str,
    locale: str,
    extra_env: Mapping[str, str] | None = None,
) -> commands.CommandResult:
    """Invoke ``lpm --sysconfig`` with the provided configuration."""

    command = [
        "lpm",
        "--sysconfig",
        f"--root={target_root}",
        f"--hostname={hostname}",
        f"--timezone={timezone}",
        f"--locale={locale}",
    ]

    LOGGER.info("Generating system configuration via lpm --sysconfig")
    return commands.run(command, env=extra_env)


def install_packages(
    packages: Sequence[str],
    target_root: Path,
    *,
    reinstall: bool = False,
    extra_env: Mapping[str, str] | None = None,
) -> commands.CommandResult | None:
    """Install packages into the target root using ``lpm``."""

    if not packages:
        LOGGER.info("No additional packages requested; skipping lpm install")
        return None

    command = ["lpm", "install", f"--root={target_root}"]
    if reinstall:
        command.append("--reinstall")
    command.extend(packages)

    LOGGER.info("Installing %d package(s) via lpm", len(packages))
    return commands.run(command, env=extra_env)
