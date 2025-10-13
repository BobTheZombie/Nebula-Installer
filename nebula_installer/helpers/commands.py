"""Command execution helpers."""

from __future__ import annotations

import logging
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class CommandResult:
    """Result of a command execution."""

    returncode: int
    stdout: str
    stderr: str


class CommandError(RuntimeError):
    """Raised when a command exits with a non-zero status."""

    def __init__(self, message: str, result: CommandResult) -> None:
        super().__init__(message)
        self.result = result


def _format_command(command: Sequence[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def run(
    command: Sequence[str],
    *,
    check: bool = True,
    capture_output: bool = True,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    input: str | None = None,
) -> CommandResult:
    """Run a command and optionally raise an error on failure."""

    LOGGER.debug("Executing: %s", _format_command(command))
    completed = subprocess.run(
        list(command),
        cwd=str(cwd) if cwd else None,
        env=dict(env) if env else None,
        capture_output=capture_output,
        text=True,
        check=False,
        input=input,
    )

    result = CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )

    if check and result.returncode != 0:
        LOGGER.error("Command failed (%s): %s", result.returncode, result.stderr.strip())
        raise CommandError(f"Command failed: {_format_command(command)}", result)

    if result.stdout:
        LOGGER.debug("stdout: %s", result.stdout.strip())
    if result.stderr:
        LOGGER.debug("stderr: %s", result.stderr.strip())

    return result
