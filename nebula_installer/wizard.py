"""Interactive setup wizard for the Nebula installer."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .config import InstallConfig
from .constants import DEFAULT_BOOTSTRAP_PACKAGES
from .textual_ui import launch_wizard

LOGGER = logging.getLogger(__name__)


def run_wizard(base_config: InstallConfig | None = None) -> InstallConfig:
    """Run the Textual-based wizard and return an :class:`InstallConfig`."""

    return launch_wizard(base_config, default_bootstrap=DEFAULT_BOOTSTRAP_PACKAGES)


def write_config(config: InstallConfig, destination: Path) -> None:
    """Persist the generated configuration to disk as JSON."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
    LOGGER.info("Wrote configuration to %s", destination)

