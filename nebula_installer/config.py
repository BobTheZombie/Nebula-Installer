"""Configuration models for the Nebula installer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Sequence


@dataclass(slots=True)
class Partition:
    """Describes a partition that should appear in ``fstab``."""

    device: str
    mountpoint: str
    filesystem: str
    options: str = "defaults"
    dump: int = 0
    passno: int = 2

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Partition":
        return cls(
            device=data["device"],
            mountpoint=data.get("mountpoint", "/"),
            filesystem=data.get("filesystem", "ext4"),
            options=data.get("options", "defaults"),
            dump=int(data.get("dump", 0)),
            passno=int(data.get("passno", 2)),
        )


@dataclass(slots=True)
class User:
    """Primary user configuration."""

    username: str
    password: str
    groups: Sequence[str] = field(default_factory=list)
    shell: str = "/bin/bash"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        return cls(
            username=data["username"],
            password=data["password"],
            groups=tuple(data.get("groups", [])),
            shell=data.get("shell", "/bin/bash"),
        )


@dataclass(slots=True)
class InstallConfig:
    """Top-level configuration consumed by the installer."""

    target_root: Path
    hostname: str
    timezone: str
    locale: str
    bootstrap_packages: Sequence[str]
    packages: Sequence[str]
    partitions: Sequence[Partition]
    user: User

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InstallConfig":
        partitions = [Partition.from_dict(item) for item in data.get("partitions", [])]
        user = User.from_dict(data["user"])
        packages: Iterable[str] = data.get("packages", [])
        bootstrap_packages: Iterable[str] = data.get(
            "bootstrap_packages",
            ("nebula-base", "linux", "kernel-modules"),
        )
        return cls(
            target_root=Path(data["target_root"]).resolve(),
            hostname=data.get("hostname", "nebula"),
            timezone=data.get("timezone", "UTC"),
            locale=data.get("locale", "en_US.UTF-8"),
            bootstrap_packages=tuple(bootstrap_packages),
            packages=tuple(packages),
            partitions=tuple(partitions),
            user=user,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_root": str(self.target_root),
            "hostname": self.hostname,
            "timezone": self.timezone,
            "locale": self.locale,
            "bootstrap_packages": list(self.bootstrap_packages),
            "packages": list(self.packages),
            "partitions": [
                {
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "filesystem": part.filesystem,
                    "options": part.options,
                    "dump": part.dump,
                    "passno": part.passno,
                }
                for part in self.partitions
            ],
            "user": {
                "username": self.user.username,
                "password": self.user.password,
                "groups": list(self.user.groups),
                "shell": self.user.shell,
            },
        }
