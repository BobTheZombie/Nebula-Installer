"""Helpers for interacting with ``lpm``."""

from __future__ import annotations

import logging
import os
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
    """Invoke ``lpm --sysconfig`` and apply additional configuration."""

    command = [
        "lpm",
        "--sysconfig",
        "--sysconfig-root",
        str(target_root),
    ]

    LOGGER.info("Generating system configuration via lpm --sysconfig")
    result = commands.run(command, env=extra_env)

    _write_hostname(target_root, hostname)
    _write_timezone(target_root, timezone)
    _write_locale(target_root, locale)

    return result


def _write_hostname(target_root: Path, hostname: str) -> None:
    hostname_path = target_root / "etc" / "hostname"
    hostname_path.parent.mkdir(parents=True, exist_ok=True)
    hostname_path.write_text(f"{hostname}\n", encoding="utf-8")
    LOGGER.info("Configured hostname at %s", hostname_path)


def _write_timezone(target_root: Path, timezone: str) -> None:
    timezone_path_obj = Path(timezone)
    if timezone_path_obj.is_absolute() or any(part == ".." for part in timezone_path_obj.parts):
        LOGGER.warning("Ignoring invalid timezone value: %s", timezone)
        return

    zoneinfo_root = target_root / "usr" / "share" / "zoneinfo"
    source = zoneinfo_root / timezone_path_obj
    if not source.exists():
        LOGGER.warning("Timezone %s not found under %s", timezone, zoneinfo_root)
        return

    timezone_path = target_root / "etc" / "timezone"
    timezone_path.parent.mkdir(parents=True, exist_ok=True)
    timezone_path.write_text(f"{timezone}\n", encoding="utf-8")

    localtime_path = target_root / "etc" / "localtime"
    try:
        if localtime_path.exists() or localtime_path.is_symlink():
            localtime_path.unlink()
        relative_target = Path("..") / "usr" / "share" / "zoneinfo" / timezone_path_obj
        os.symlink(relative_target, localtime_path)
    except OSError as exc:
        LOGGER.warning("Unable to link localtime for timezone %s: %s", timezone, exc)
    else:
        LOGGER.info("Configured timezone using %s", localtime_path)


def _write_locale(target_root: Path, locale: str) -> None:
    locale_conf_path = target_root / "etc" / "locale.conf"
    locale_conf_path.parent.mkdir(parents=True, exist_ok=True)
    locale_conf_content = f"LANG={locale}\nLC_CTYPE={locale}\n"
    locale_conf_path.write_text(locale_conf_content, encoding="utf-8")

    locale_gen_path = target_root / "etc" / "locale.gen"
    base, _, encoding = locale.partition(".")
    if not encoding:
        encoding = "UTF-8"
    entry = f"{base}.{encoding} {encoding}"
    if locale_gen_path.exists():
        lines = locale_gen_path.read_text(encoding="utf-8").splitlines()
        if entry in lines:
            LOGGER.info("Locale %s already present in %s", locale, locale_gen_path)
        else:
            lines.append(entry)
            locale_gen_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            LOGGER.info("Added locale %s to %s", locale, locale_gen_path)
    else:
        locale_gen_path.parent.mkdir(parents=True, exist_ok=True)
        locale_gen_path.write_text(entry + "\n", encoding="utf-8")
        LOGGER.info("Created %s with locale %s", locale_gen_path, locale)

    try:
        result = commands.run(["locale-gen", "--root", str(target_root)], check=False)
    except FileNotFoundError:
        LOGGER.info("locale-gen not available; skipping locale archive generation")
    else:
        if result.returncode != 0:
            LOGGER.warning("locale-gen reported an error for %s", locale)
        else:
            LOGGER.info("locale-gen executed for %s", locale)


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

    command = ["lpm", "install", "--root", str(target_root)]
    if reinstall:
        command.append("--reinstall")
    command.extend(packages)

    LOGGER.info("Installing %d package(s) via lpm", len(packages))
    return commands.run(command, env=extra_env)
