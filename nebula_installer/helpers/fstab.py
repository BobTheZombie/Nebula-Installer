"""Helpers to manage ``fstab`` entries using the new helper script."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Sequence

from ..config import Partition
from . import commands

LOGGER = logging.getLogger(__name__)


def build_fstab_lines(partitions: Sequence[Partition]) -> Iterable[str]:
    """Construct fstab entries for the provided partitions."""

    for part in partitions:
        mountpoint = part.mountpoint if part.mountpoint.startswith("/") else f"/{part.mountpoint}"
        yield f"{part.device}\t{mountpoint}\t{part.filesystem}\t{part.options}\t{part.dump}\t{part.passno}"


def write_fstab(target_root: Path, partitions: Sequence[Partition]) -> Path:
    """Write ``/etc/fstab`` within the target root using the helper output."""

    fstab_path = target_root / "etc" / "fstab"
    fstab_path.parent.mkdir(parents=True, exist_ok=True)
    lines = list(build_fstab_lines(partitions))

    LOGGER.info("Writing %d fstab entries via helper", len(lines))
    content = "\n".join(lines) + "\n"
    fstab_path.write_text(content, encoding="utf-8")
    return fstab_path


def sync_mounts(target_root: Path) -> None:
    """Invoke the helper script to apply the fstab within the target root."""

    helper_command = ["nebula-fstab-helper", f"--root={target_root}"]
    try:
        commands.run(helper_command)
    except commands.CommandError as exc:  # pragma: no cover - logging path
        LOGGER.warning("fstab helper failed: %s", exc)
        raise
