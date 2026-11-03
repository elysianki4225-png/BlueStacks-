"""High-level, safe operations on BlueStacks configuration files."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Iterable, Mapping

from .backup import create_backup
from .config_store import ConfigStore
from .constants import (
    ADB_PORT_FIELD,
    BRAND_FIELD,
    DPI_FIELD,
    HEIGHT_FIELD,
    MANUFACTURER_FIELD,
    MODEL_FIELD,
    PROFILE_CODE_FIELD,
    ROOT_FIELD,
    STATUS_ADB_PORT_FIELD,
    WIDTH_FIELD,
)
from .discovery import detect_running_processes
from .models import Installation, OperationResult
from .random_device import generate_device
from .safety import validate_config_path


def _ensure_instance(store: ConfigStore, instance_id: str, *, create: bool = False) -> None:
    if instance_id not in store.instance_ids():
        if create:
            store.add_instance_id(instance_id)
        else:
            raise ValueError(f"实例不存在: {instance_id}")


def _prepare_write(
    config_path: str | Path,
    *,
    auto_backup: bool = True,
    backup_note: str = "",
) -> tuple[ConfigStore, Path, object | None]:
    path = validate_config_path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    store = ConfigStore.load(path)
    backup = create_backup(path, note=backup_note) if auto_backup else None
    return store, path, backup


def stop_bluestacks_processes(*, force: bool = False) -> list[str]:
    """Stop BlueStacks processes.

    This is intentionally not part of normal write flows. The UI asks for
    confirmation; ``force`` is required to actually terminate processes.
    """

    if not force:
        return []
    if platform.system() != "Windows":
        return []
    names = sorted(detect_running_processes())
    stopped: list[str] = []
    for name in names:
        try:
            result = subprocess.run(
                ["taskkill", "/IM", name, "/F"],
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="ignore",
            )
            if result.returncode == 0:
                stopped.append(name)
        except OSError:
            continue
    return stopped


def set_root(
    config_path: str | Path,
    instance_ids: Iterable[str],
    enabled: bool,
    *,
    auto_backup: bool = True,
    create_instance: bool = False,
    backup_note: str = "",
) -> OperationResult:
    """Enable or disable Root access for one or more instances."""

    store, path, backup = _prepare_write(config_path, auto_backup=auto_backup, backup_note=backup_note)
    selected = list(instance_ids)
    changes: dict[str, dict[str, str]] = {}
    warnings: list[str] = []
    value = "1" if enabled else "0"
    for instance_id in selected:
        _ensure_instance(store, instance_id, create=create_instance)
        changed = store.set_instance_values(instance_id, {ROOT_FIELD: value})
        if changed:
            changes[instance_id] = changed
    if not changes:
        return OperationResult(changed=False, backup=backup, changes={}, warnings=warnings)
    store.save(create_backup=False)
    return OperationResult(changed=True, backup=backup, changes=changes, warnings=warnings)


def set_device(
    config_path: str | Path,
    instance_ids: Iterable[str],
    device: Mapping[str, object],
    *,
    auto_backup: bool = True,
    create_instance: bool = False,
    backup_note: str = "",
) -> OperationResult:
    """Apply a device profile to one or more instances."""

    store, path, backup = _prepare_write(config_path, auto_backup=auto_backup, backup_note=backup_note)
    selected = list(instance_ids)
    profile_code = str(device.get("profile_code", "") or "")
    brand = str(device.get("brand", "") or "")
    manufacturer = str(device.get("manufacturer", "") or "")
    model = str(device.get("model", "") or "")
    width = device.get("width")
    height = device.get("height")
    dpi = device.get("dpi")
    values: dict[str, str] = {}
    if profile_code:
        values[PROFILE_CODE_FIELD] = profile_code
    if brand:
        values[BRAND_FIELD] = brand
    if manufacturer:
        values[MANUFACTURER_FIELD] = manufacturer
    if model:
        values[MODEL_FIELD] = model
    if width is not None:
        values[WIDTH_FIELD] = str(int(width))
    if height is not None:
        values[HEIGHT_FIELD] = str(int(height))
    if dpi is not None:
        values[DPI_FIELD] = str(int(dpi))
    if not values:
        raise ValueError("未提供任何机型字段")

    changes: dict[str, dict[str, str]] = {}
    warnings: list[str] = []
    for instance_id in selected:
        _ensure_instance(store, instance_id, create=create_instance)
        changed = store.set_instance_values(instance_id, values)
        if changed:
            changes[instance_id] = changed
    if not changes:
        return OperationResult(changed=False, backup=backup, changes={}, warnings=warnings)
    store.save(create_backup=False)
    return OperationResult(changed=True, backup=backup, changes=changes, warnings=warnings)


def random_device_for_instances(
    config_path: str | Path,
    instance_ids: Iterable[str],
    *,
    manufacturer: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    profile_code: str | None = None,
    auto_backup: bool = True,
    create_instance: bool = False,
    backup_note: str = "",
) -> OperationResult:
    """Generate and apply a random device profile to selected instances."""

    device = generate_device(
        manufacturer=manufacturer,
        brand=brand,
        model=model,
        profile_code=profile_code,
    )
    return set_device(
        config_path,
        instance_ids,
        device,
        auto_backup=auto_backup,
        create_instance=create_instance,
        backup_note=backup_note,
    )


def resolve_installation(installation: Installation) -> Path:
    return validate_config_path(installation.config_path)
