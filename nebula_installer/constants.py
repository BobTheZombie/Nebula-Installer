"""Shared constants for the Nebula Installer."""

from __future__ import annotations

from typing import Sequence

# Default packages used when bootstrapping a fresh system. These values are
# intentionally shared between the CLI wizard and the Textual interface.
DEFAULT_BOOTSTRAP_PACKAGES: Sequence[str] = (
    "luminos-base",
    "linux",
    "kernel-modules",
)

