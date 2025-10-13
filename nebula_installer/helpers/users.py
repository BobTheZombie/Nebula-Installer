"""User management helpers for the installer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from . import commands

LOGGER = logging.getLogger(__name__)


def ensure_user(
    target_root: Path,
    username: str,
    password: str,
    groups: Sequence[str],
    shell: str,
) -> None:
    """Create or update the primary user inside the target root."""

    command = [
        "chroot",
        str(target_root),
        "useradd",
        "--create-home",
        "--shell",
        shell,
        "--password",
        password,
    ]
    if groups:
        command.extend(["--groups", ",".join(groups)])
    command.append(username)

    LOGGER.info("Ensuring user %s exists in target root", username)
    try:
        commands.run(command)
    except commands.CommandError as exc:
        # If the user already exists we update their password and group membership.
        LOGGER.warning("useradd failed, attempting to update existing user: %s", exc)
        passwd_cmd = ["chroot", str(target_root), "chpasswd", "-e"]
        input_payload = f"{username}:{password}\n"
        commands.run(passwd_cmd, capture_output=False, input=input_payload)
        usermod_cmd = [
            "chroot",
            str(target_root),
            "usermod",
            "--shell",
            shell,
        ]
        if groups:
            usermod_cmd.extend(["--groups", ",".join(groups)])
        usermod_cmd.append(username)
        commands.run(usermod_cmd)
