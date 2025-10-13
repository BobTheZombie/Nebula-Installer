"""Interactive setup wizard for Nebula installer."""

from __future__ import annotations

import getpass
import json
import logging
from pathlib import Path
from typing import List, Sequence

import crypt

from .config import InstallConfig, Partition, User

LOGGER = logging.getLogger(__name__)

DEFAULT_BOOTSTRAP_PACKAGES: Sequence[str] = (
    "nebula-base",
    "linux",
    "kernel-modules",
)


def _prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    response = input(f"{text}{suffix}: ").strip()
    if not response and default is not None:
        return default
    return response


def _prompt_list(prompt: str, default: Sequence[str] | None = None) -> List[str]:
    default_str = ", ".join(default) if default else ""
    raw = _prompt(prompt, default_str if default_str else None)
    if not raw:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


def _prompt_bootstrap_packages(default: Sequence[str] | None) -> List[str]:
    return _prompt_list(
        "Bootstrap packages to install via lpm",
        default or DEFAULT_BOOTSTRAP_PACKAGES,
    )


def _prompt_additional_packages(default: Sequence[str] | None) -> List[str]:
    return _prompt_list("Additional packages (comma separated)", default or [])


def _prompt_partitions(existing: Sequence[Partition] | None) -> List[Partition]:
    print("\nDefine the filesystems that should appear in /etc/fstab.")
    print("Leave the device blank when you are finished. At least one entry is required.\n")

    partitions: List[Partition] = []
    defaults = list(existing or [])
    index = 0
    while True:
        default_part = defaults[index] if index < len(defaults) else None
        device_default = default_part.device if default_part else None
        device = _prompt("Device (e.g. /dev/sda1)", device_default)
        if not device:
            if partitions:
                break
            print("At least one partition is required. Please enter the root filesystem.")
            continue
        mount_default = default_part.mountpoint if default_part else "/"
        mount = _prompt("Mountpoint", mount_default)
        fs_default = default_part.filesystem if default_part else "ext4"
        filesystem = _prompt("Filesystem", fs_default)
        options_default = default_part.options if default_part else "defaults"
        options = _prompt("Mount options", options_default)
        dump_default = str(default_part.dump) if default_part else "0"
        dump = int(_prompt("Dump flag", dump_default) or dump_default)
        pass_default = str(default_part.passno) if default_part else "2"
        passno = int(_prompt("Pass number", pass_default) or pass_default)
        partitions.append(
            Partition(
                device=device,
                mountpoint=mount,
                filesystem=filesystem,
                options=options,
                dump=dump,
                passno=passno,
            )
        )
        index += 1
    return partitions


def _prompt_user(existing: User | None) -> User:
    username = _prompt("Primary username", existing.username if existing else "nebula")
    print("Enter the password for the new user. It will be stored hashed using SHA-512.")
    while True:
        raw_password = getpass.getpass(f"Password for {username}: ")
        confirm = getpass.getpass("Confirm password: ")
        if raw_password != confirm:
            print("Passwords do not match. Try again.")
            continue
        if not raw_password:
            print("Password cannot be empty.")
            continue
        break
    hashed_password = crypt.crypt(raw_password, crypt.mksalt(crypt.METHOD_SHA512))
    groups_default = ", ".join(existing.groups) if existing and existing.groups else "wheel"
    groups = _prompt_list("Supplementary groups", groups_default.split(", ") if groups_default else [])
    shell = _prompt("Login shell", existing.shell if existing else "/bin/bash")
    return User(
        username=username,
        password=hashed_password,
        groups=tuple(groups),
        shell=shell,
    )


def _resolve_target_root(value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve()


def run_wizard(base_config: InstallConfig | None = None) -> InstallConfig:
    print("Nebula Installer interactive setup\n")
    default_root = str(base_config.target_root) if base_config else "/mnt/nebula"
    target_root = _resolve_target_root(_prompt("Target root directory", default_root))
    hostname = _prompt("Hostname", base_config.hostname if base_config else "nebula")
    timezone = _prompt("Timezone", base_config.timezone if base_config else "UTC")
    locale = _prompt("Locale", base_config.locale if base_config else "en_US.UTF-8")

    bootstrap_packages = _prompt_bootstrap_packages(
        base_config.bootstrap_packages if base_config else DEFAULT_BOOTSTRAP_PACKAGES
    )
    packages = _prompt_additional_packages(base_config.packages if base_config else [])
    partitions = _prompt_partitions(base_config.partitions if base_config else [])
    user = _prompt_user(base_config.user if base_config else None)

    return InstallConfig(
        target_root=target_root,
        hostname=hostname,
        timezone=timezone,
        locale=locale,
        bootstrap_packages=tuple(bootstrap_packages),
        packages=tuple(packages),
        partitions=tuple(partitions),
        user=user,
    )


def write_config(config: InstallConfig, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
    LOGGER.info("Wrote configuration to %s", destination)
