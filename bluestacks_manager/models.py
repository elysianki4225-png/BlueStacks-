"""Typed models shared by the API and UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DeviceProfile:
    """A device model/profile as represented in bluestacks.conf."""

    profile_code: str = ""
    brand: str = ""
    manufacturer: str = ""
    model: str = ""
    width: int = 0
    height: int = 0
    dpi: int = 0

    @property
    def is_custom(self) -> bool:
        return bool(self.brand or self.manufacturer or self.model)

    @property
    def display_name(self) -> str:
        if self.is_custom:
            parts = [self.manufacturer, self.brand, self.model]
            return " ".join(part for part in parts if part)
        return self.profile_code or "未命名机型"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InstanceConfig:
    """A single BlueStacks instance plus its resolved paths."""

    instance_id: str
    display_name: str
    config_path: str
    root_enabled: bool
    device: DeviceProfile
    width: int = 0
    height: int = 0
    dpi: int = 0
    adb_port: str = ""
    instance_dir: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "display_name": self.display_name,
            "config_path": self.config_path,
            "root_enabled": self.root_enabled,
            "device": self.device.to_dict(),
            "width": self.width,
            "height": self.height,
            "dpi": self.dpi,
            "adb_port": self.adb_port,
            "instance_dir": self.instance_dir,
            "warnings": list(self.warnings),
        }


@dataclass
class Installation:
    """A detected BlueStacks installation and its primary config file."""

    source: str
    user_path: str
    data_path: str
    install_path: str
    version: str
    config_path: str
    config_exists: bool
    instance_count: int
    patch_mode: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BackupRecord:
    """A timestamped backup file."""

    backup_id: str
    original_path: str
    backup_path: str
    created_at: str
    size: int
    sha256: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OperationResult:
    """Result returned after a config write."""

    changed: bool
    backup: BackupRecord | None
    changes: dict[str, dict[str, str]]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed": self.changed,
            "backup": self.backup.to_dict() if self.backup else None,
            "changes": self.changes,
            "warnings": list(self.warnings),
        }
