"""Graphical install plan and command routing checks (no disks are touched)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nebula_installer.config import InstallConfig, Partition, User
from nebula_installer.graphical_backend import (
    PlanError, package_names, partition_rows, validate_plan,
)
from nebula_installer.helpers import lpm
from nebula_installer.helpers.commands import CommandResult


def _config(target=Path("/mnt/lpm"), mode="repository"):
    return InstallConfig(
        target_root=target, hostname="lpm-linux", timezone="America/Detroit",
        locale="en_US.UTF-8", bootstrap_packages=(),
        packages=("plasma6-full",),
        partitions=(Partition("/dev/vda2", "/", "ext4"),),
        user=User(username="lpmuser", password="$6$test$hash", groups=("wheel",)),
        install_mode=mode, register_grub_hook=False, sync_fstab_mounts=False,
    )


def test_refuses_install_to_live_host_root():
    with pytest.raises(PlanError, match="live system root"):
        validate_plan(_config(target=Path("/")), check_environment=False)


def test_requires_exact_confirmed_target():
    with pytest.raises(PlanError, match="Confirmed destination differs"):
        validate_plan(_config(), confirmed_target=Path("/mnt/not-lpm"),
                      check_environment=False)


@pytest.mark.parametrize("mode", ["repository", "source"])
def test_accepts_valid_mode(mode):
    validate_plan(_config(mode=mode), check_environment=False)


def test_rejects_command_like_packages():
    with pytest.raises(PlanError):
        package_names("plasma6-full ; rm -rf /")


def test_parses_root_and_efi_partitions():
    parts = partition_rows("/dev/vda2", "ext4", "/dev/vda1 | /boot | vfat | umask=0077")
    assert parts[0].mountpoint == "/"
    assert parts[1].mountpoint == "/boot"
    assert parts[1].passno == 0


def test_source_build_executes_inside_chroot(monkeypatch, tmp_path):
    lpm_binary = tmp_path / "usr/bin/lpm"
    lpm_binary.parent.mkdir(parents=True)
    lpm_binary.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(lpm.lpmspec, "get_cached_lpmspec", lambda: None)
    called = []
    def fake_run(argv, **kwargs):
        called.append(argv)
        return CommandResult(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(lpm.commands, "run", fake_run)
    lpm.build_packages_in_chroot(["plasma6-full"], tmp_path)
    assert called == [[
        "chroot", str(tmp_path), "/usr/bin/env", "-i",
        "HOME=/root", "PATH=/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/bin",
        "/usr/bin/lpm", "buildpkg", "plasma6-full", "--yes",
    ]]


def test_target_must_be_an_existing_mount(monkeypatch, tmp_path):
    monkeypatch.setattr("nebula_installer.graphical_backend.os.path.ismount", lambda _: False)
    with pytest.raises(PlanError, match="explicitly mounted"):
        validate_plan(_config(target=tmp_path))


def test_malformed_fstab_lines_rejected():
    with pytest.raises(PlanError, match="Partition line"):
        partition_rows("/dev/vda2", "ext4", "/dev/vda1 /boot vfat")


def test_default_existing_cli_config_is_unchanged():
    from nebula_installer.constants import DEFAULT_BOOTSTRAP_PACKAGES
    data = {
        "target_root": "/mnt/luminos", "user": {"username": "demo", "password": "$6$hash"},
        "partitions": [{"device": "/dev/vda2", "mountpoint": "/", "filesystem": "ext4"}],
    }
    config = InstallConfig.from_dict(data)
    assert config.install_mode == "repository"
    assert config.register_grub_hook is True
    assert tuple(config.bootstrap_packages) == tuple(DEFAULT_BOOTSTRAP_PACKAGES)
