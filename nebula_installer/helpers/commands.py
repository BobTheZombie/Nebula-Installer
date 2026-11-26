"""Command execution helpers."""

from __future__ import annotations

import logging
import os
import sys
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
    if os.environ.get("NEBULA_STREAM_COMMANDS") == "1" and capture_output and input is None:
        # The privileged GUI worker streams installer logs to its QProcess client.
        # Only the worker activates this mode; secrets submitted on stdin never
        # enter this output path.
        process = subprocess.Popen(
            list(command),
            cwd=str(cwd) if cwd else None,
            env=dict(env) if env else None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=1, text=True,
        )
        output: list[str] = []
        size = 0
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            output.append(line)
            size += len(line)
            if size > 262144:
                output = output[-300:]
                size = sum(len(item) for item in output)
        process.stdout.close()
        result = CommandResult(process.wait(), "".join(output), "")
    else:
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
