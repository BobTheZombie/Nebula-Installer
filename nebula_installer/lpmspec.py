"""Utilities for loading and working with LPM ``lpmspec`` descriptions."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

LOGGER = logging.getLogger(__name__)

# Environment variable recognised by the installer to override the location of
# the lpmspec JSON description exported by LPM.
ENV_LPMSPEC_PATH = "NEBULA_LPMSPEC_PATH"

# Default lpmspec location mirrors the maintainer output path used by LPM.
DEFAULT_LPMSPEC_PATH = Path("/var/lib/lpm/maintainer/lpmspec.json")


class LPMSpecError(RuntimeError):
    """Base error raised when an lpmspec document cannot be processed."""


class LPMSpecValidationError(LPMSpecError):
    """Raised when the lpmspec document is missing required fields."""


@dataclass(slots=True)
class CLIArgument:
    """Represents an individual CLI argument in the lpmspec document."""

    name: str
    flags: tuple[str, ...]
    help: str
    positional: bool
    required: bool = False
    metavar: str | None = None
    nargs: str | int | None = None
    choices: tuple[str, ...] = ()
    default: Any = None
    type: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CLIArgument":
        if not isinstance(data, Mapping):
            raise LPMSpecValidationError("CLI argument entry must be a mapping")

        name = str(data.get("name"))
        if not name:
            raise LPMSpecValidationError("CLI argument entry missing 'name'")

        flags: Iterable[str] = data.get("flags", [])
        if not isinstance(flags, Sequence):
            raise LPMSpecValidationError("CLI argument 'flags' must be an array")

        help_text = str(data.get("help", ""))
        positional = bool(data.get("positional", False))
        required = bool(data.get("required", False))

        metavar = data.get("metavar")
        if metavar is not None:
            metavar = str(metavar)

        nargs = data.get("nargs")
        if isinstance(nargs, (int, str)):
            parsed_nargs: str | int | None = nargs
        elif nargs is None:
            parsed_nargs = None
        else:
            raise LPMSpecValidationError("CLI argument 'nargs' must be int, str, or null")

        raw_choices = data.get("choices")
        if raw_choices is None:
            choices: tuple[str, ...] = ()
        elif isinstance(raw_choices, Sequence):
            choices = tuple(str(choice) for choice in raw_choices)
        else:
            raise LPMSpecValidationError("CLI argument 'choices' must be an array if present")

        arg_type = data.get("type")
        if arg_type is not None:
            arg_type = str(arg_type)

        return cls(
            name=name,
            flags=tuple(str(flag) for flag in flags),
            help=help_text,
            positional=positional,
            required=required,
            metavar=metavar,
            nargs=parsed_nargs,
            choices=choices,
            default=data.get("default"),
            type=arg_type,
        )

    def has_flag(self, flag: str) -> bool:
        """Return ``True`` if the argument exposes the provided option flag."""

        return (not self.positional) and flag in self.flags


@dataclass(slots=True)
class CLICommand:
    """Represents a sub-command in the LPM CLI."""

    name: str
    help: str
    usage: str
    description: str
    arguments: tuple[CLIArgument, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CLICommand":
        if not isinstance(data, Mapping):
            raise LPMSpecValidationError("CLI command entry must be a mapping")

        name = str(data.get("name"))
        if not name:
            raise LPMSpecValidationError("CLI command entry missing 'name'")

        arguments_data = data.get("arguments", [])
        if not isinstance(arguments_data, Sequence):
            raise LPMSpecValidationError("CLI command 'arguments' must be an array")

        arguments = tuple(CLIArgument.from_dict(item) for item in arguments_data)
        return cls(
            name=name,
            help=str(data.get("help", "")),
            usage=str(data.get("usage", "")),
            description=str(data.get("description", "")),
            arguments=arguments,
        )

    def find_argument_by_flag(self, flag: str) -> CLIArgument | None:
        """Return the first argument exposing ``flag`` or ``None``."""

        for argument in self.arguments:
            if argument.has_flag(flag):
                return argument
        return None


@dataclass(slots=True)
class CLISpec:
    """Top-level CLI description exported by LPM."""

    usage: str
    description: str
    arguments: tuple[CLIArgument, ...]
    commands: tuple[CLICommand, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CLISpec":
        if not isinstance(data, Mapping):
            raise LPMSpecValidationError("CLI specification must be a mapping")

        arguments_data = data.get("arguments", [])
        if not isinstance(arguments_data, Sequence):
            raise LPMSpecValidationError("CLI 'arguments' must be an array")

        commands_data = data.get("commands", [])
        if not isinstance(commands_data, Sequence):
            raise LPMSpecValidationError("CLI 'commands' must be an array")

        arguments = tuple(CLIArgument.from_dict(item) for item in arguments_data)
        commands = tuple(CLICommand.from_dict(item) for item in commands_data)
        return cls(
            usage=str(data.get("usage", "")),
            description=str(data.get("description", "")),
            arguments=arguments,
            commands=commands,
        )

    def find_argument_by_flag(self, flag: str) -> CLIArgument | None:
        """Return the global argument exposing ``flag`` or ``None``."""

        for argument in self.arguments:
            if argument.has_flag(flag):
                return argument
        return None

    def get_command(self, name: str) -> CLICommand | None:
        """Return the command with ``name`` if present."""

        for command in self.commands:
            if command.name == name:
                return command
        return None


@dataclass(slots=True)
class LPMSpec:
    """Represents the entire lpmspec document."""

    api_version: str
    generated_at: int
    lpm: Mapping[str, str]
    cli: CLISpec

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LPMSpec":
        if not isinstance(data, Mapping):
            raise LPMSpecValidationError("lpmspec root must be a mapping")

        try:
            api_version = str(data["api_version"])
            generated_at = int(data["generated_at"])
            lpm_raw = data["lpm"]
            cli_raw = data["cli"]
        except KeyError as exc:
            raise LPMSpecValidationError(f"lpmspec missing required field: {exc.args[0]}") from exc
        except (TypeError, ValueError) as exc:
            raise LPMSpecValidationError("lpmspec contains invalid field types") from exc

        if not isinstance(lpm_raw, Mapping):
            raise LPMSpecValidationError("lpmspec 'lpm' field must be a mapping")

        lpm_metadata = {str(key): str(value) for key, value in lpm_raw.items()}

        cli_spec = CLISpec.from_dict(cli_raw)
        return cls(
            api_version=api_version,
            generated_at=generated_at,
            lpm=lpm_metadata,
            cli=cli_spec,
        )

    @property
    def lpm_name(self) -> str:
        """Convenience accessor for the LPM product name."""

        return self.lpm.get("name", "LPM")

    @property
    def lpm_version(self) -> str | None:
        """Return the LPM version string if available."""

        return self.lpm.get("version")

    @property
    def lpm_build(self) -> str | None:
        """Return the LPM build identifier if available."""

        return self.lpm.get("build")


def resolve_lpmspec_path(path: Path | str | None = None) -> Path:
    """Resolve the lpmspec path honouring environment overrides."""

    if path is not None:
        return Path(path)

    env_override = os.environ.get(ENV_LPMSPEC_PATH)
    if env_override:
        return Path(env_override)

    return DEFAULT_LPMSPEC_PATH


def load_lpmspec(path: Path | str | None = None) -> LPMSpec:
    """Load and parse the lpmspec JSON document from ``path``."""

    resolved = resolve_lpmspec_path(path)
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except Exception as exc:  # pragma: no cover - unexpected IO failure
        raise LPMSpecError(f"Unable to read lpmspec at {resolved}: {exc}") from exc

    if not isinstance(data, Mapping):
        raise LPMSpecValidationError("lpmspec root must be a JSON object")

    return LPMSpec.from_dict(data)


@lru_cache(maxsize=None)
def _cached_load(path: str) -> LPMSpec | None:
    try:
        return load_lpmspec(Path(path))
    except FileNotFoundError:
        LOGGER.debug("lpmspec not found at %s", path)
        return None
    except LPMSpecError as exc:
        LOGGER.warning("Unable to load lpmspec from %s: %s", path, exc)
        return None


def get_cached_lpmspec(path: Path | str | None = None) -> LPMSpec | None:
    """Return a cached lpmspec instance or ``None`` if unavailable."""

    resolved = resolve_lpmspec_path(path)
    return _cached_load(str(resolved))


def clear_cached_lpmspec() -> None:
    """Clear the cached lpmspec instance (useful for testing)."""

    _cached_load.cache_clear()

