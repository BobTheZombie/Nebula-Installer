"""Command line entry point for the Nebula Installer for LuminOS."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .installer import Installer, load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nebula Installer for LuminOS")
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to the installation configuration JSON file",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the Qt 6 graphical LPM Linux installer",
    )
    parser.add_argument(
        "--apply-stdin",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--confirm-target",
        type=Path,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run the interactive setup wizard",
    )
    parser.add_argument(
        "--write-config",
        type=Path,
        help="Optional path to save the generated configuration when using --interactive",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s:%(name)s:%(message)s",
    )
    if args.gui:
        from .graphical_ui import run_graphical
        run_graphical()
        return
    if args.apply_stdin:
        from .graphical_backend import apply_stdin
        apply_stdin(args.confirm_target)
        return
    if not args.interactive and not args.config:
        raise SystemExit("Provide --config, --interactive, or --gui.")

    from .wizard import run_wizard, write_config
    base_config = load_config(args.config) if args.config else None

    if args.interactive:
        config = run_wizard(base_config)
        if args.write_config:
            write_config(config, args.write_config)
    else:
        config = base_config
        if config is None:
            raise SystemExit("Failed to load configuration from provided path.")

    installer = Installer(config)
    installer.run()


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
