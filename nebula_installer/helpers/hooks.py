"""Post-install hooks such as ``update-grub``."""

from __future__ import annotations

import logging
import os
from pathlib import Path

LOGGER = logging.getLogger(__name__)


UPDATE_GRUB_HOOK = "zz-update-grub"


def register_update_grub_hook(target_root: Path) -> Path:
    """Ensure the update-grub hook exists inside the target root."""

    hook_dir = target_root / "etc" / "kernel" / "postinst.d"
    hook_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hook_dir / UPDATE_GRUB_HOOK

    script = "#!/bin/sh\nset -e\nupdate-grub\n"
    hook_path.write_text(script, encoding="utf-8")
    os.chmod(hook_path, 0o755)
    LOGGER.info("Registered update-grub hook at %s", hook_path)
    return hook_path
