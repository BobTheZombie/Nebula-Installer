"""High level orchestration for the Nebula installer."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .config import InstallConfig
from .helpers import commands, fstab, hooks, lpm
from .helpers import users as user_helpers

LOGGER = logging.getLogger(__name__)


class Installer:
    """Main entry point coordinating the installation workflow."""

    def __init__(self, config: InstallConfig) -> None:
        self.config = config

    def run(self) -> None:
        LOGGER.info("Starting LPM Linux installation (%s) into %s", self.config.install_mode, self.config.target_root)
        self.config.target_root.mkdir(parents=True, exist_ok=True)
        self._bootstrap_base_system()
        self._generate_sysconfig()
        self._install_packages()
        self._configure_fstab()
        self._register_hooks()
        self._ensure_user()
        LOGGER.info("LPM Linux installation complete")

    def _bootstrap_base_system(self) -> None:
        LOGGER.debug("Bootstrapping base system packages")
        lpm.install_packages(
            self.config.bootstrap_packages,
            self.config.target_root,
        )

    def _generate_sysconfig(self) -> None:
        LOGGER.debug("Generating base sysconfig")
        lpm.generate_sysconfig(
            self.config.target_root,
            hostname=self.config.hostname,
            timezone=self.config.timezone,
            locale=self.config.locale,
        )

    def _install_packages(self) -> None:
        LOGGER.debug("Installing packages")
        if self.config.install_mode == "source":
            lpm.build_packages_in_chroot(self.config.packages, self.config.target_root)
        elif self.config.install_mode == "repository":
            lpm.install_packages(self.config.packages, self.config.target_root)
        else:
            raise ValueError("Unknown installation mode")

    def _configure_fstab(self) -> None:
        LOGGER.debug("Writing fstab entries")
        fstab_path = fstab.write_fstab(self.config.target_root, self.config.partitions)
        LOGGER.info("fstab written to %s", fstab_path)
        if self.config.sync_fstab_mounts:
            try:
                fstab.sync_mounts(self.config.target_root)
            except commands.CommandError:
                LOGGER.warning("Continuing despite fstab helper failure")

    def _register_hooks(self) -> None:
        LOGGER.debug("Registering update-grub hook")
        if self.config.register_grub_hook:
            hooks.register_update_grub_hook(self.config.target_root)

    def _ensure_user(self) -> None:
        LOGGER.debug("Ensuring default user")
        user_helpers.ensure_user(
            self.config.target_root,
            username=self.config.user.username,
            password=self.config.user.password,
            groups=self.config.user.groups,
            shell=self.config.user.shell,
        )


def load_config(path: Path) -> InstallConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    config = InstallConfig.from_dict(data)
    return config
