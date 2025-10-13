"""Command line entry point for the Nebula installer."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .installer import Installer, load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nebula OS installer")
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to the installation configuration JSON file",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s:%(name)s:%(message)s",
    )
    config = load_config(args.config)
    installer = Installer(config)
    installer.run()


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
