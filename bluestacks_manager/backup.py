"""Backup and restore utilities for BlueStacks configuration files."""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from .config_store import backup_config_file
from .models import BackupRecord
from .safety import backup_directory, resolve_backup, sha256_file


def create_backup(config_path: str | Path, note: str = "") -> BackupRecord:
    """Create a timestamped backup of a BlueStacks config file."""

    source = Path(config_path).expanduser()
    if not source.exists():
        raise FileNotFoundError(f"配置文件不存在: {source}")
    backup_path = backup_config_file(source)
    record = BackupRecord(
        backup_id=backup_path.name,
        original_path=str(source),
        backup_path=str(backup_path),
        created_at=datetime.fromtimestamp(backup_path.stat().st_mtime).isoformat(timespec="seconds"),
        size=backup_path.stat().st_size,
        sha256=sha256_file(backup_path),
        note=note,
    )
    return record


def list_backups(config_path: str | Path) -> list[dict[str, object]]:
    """List backups for a config path."""

    from .safety import list_backups as _list_backups

    return _list_backups(config_path)


def restore_backup(backup_id: str, config_path: str | Path) -> BackupRecord:
    """Restore a backup to the target config path atomically."""

    target = Path(config_path).expanduser()
    source = resolve_backup(backup_id, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=".bluestacks.conf.restore.",
        suffix=".tmp",
    )
    try:
        os.close(temp_fd)
        shutil.copy2(source, temp_path)
        os.replace(temp_path, target)
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
    return BackupRecord(
        backup_id=source.name,
        original_path=str(target),
        backup_path=str(source),
        created_at=datetime.fromtimestamp(source.stat().st_mtime).isoformat(timespec="seconds"),
        size=source.stat().st_size,
        sha256=sha256_file(source),
        note="已恢复到目标文件",
    )


def delete_backup(backup_id: str, config_path: str | Path) -> None:
    """Delete a backup file."""

    source = resolve_backup(backup_id, config_path)
    source.unlink()


def backup_directory_for(config_path: str | Path) -> Path:
    return backup_directory(config_path)
