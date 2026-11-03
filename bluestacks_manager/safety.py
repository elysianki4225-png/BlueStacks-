"""Preflight checks and validation helpers.

These functions deliberately avoid mutating anything. They are used by the API
before writes so the UI can warn about running instances, missing config files,
writable paths, backup state, and newer BlueStacks root compatibility.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable

from .config_store import ConfigStore
from .discovery import detect_running_processes, parse_version
from .models import Installation


def validate_config_path(config_path: str | Path) -> Path:
    """Validate and resolve a BlueStacks config path."""

    path = Path(config_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def sha256_file(path: str | Path) -> str:
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def config_is_writable(config_path: str | Path) -> bool:
    path = Path(config_path)
    if not path.exists():
        return False
    return os.access(path, os.W_OK)


def backup_directory(config_path: str | Path) -> Path:
    return Path(config_path).expanduser().parent / "bluestacks-manager-backups"


def list_backups(config_path: str | Path) -> list[dict[str, object]]:
    path = Path(config_path).expanduser()
    directory = backup_directory(path)
    if not directory.exists():
        return []
    backups = []
    for entry in sorted(directory.glob("*.bak"), reverse=True):
        try:
            backups.append(
                {
                    "backup_id": entry.name,
                    "original_path": str(path),
                    "backup_path": str(entry),
                    "created_at": entry.stat().st_mtime,
                    "size": entry.stat().st_size,
                    "sha256": sha256_file(entry),
                }
            )
        except OSError:
            continue
    return backups


def resolve_backup(backup_id: str, config_path: str | Path) -> Path:
    """Resolve a backup id to a file path under the config's backup directory."""

    safe_id = Path(backup_id).name
    if safe_id != backup_id or not safe_id.endswith(".bak"):
        raise ValueError("备份 ID 无效")
    directory = backup_directory(config_path)
    candidate = (directory / safe_id).resolve()
    if directory.resolve() not in candidate.parents:
        raise ValueError("备份路径越界")
    if not candidate.exists():
        raise FileNotFoundError(f"备份不存在: {candidate}")
    return candidate


def is_newer_root_patch_build(version: str) -> bool:
    parsed = parse_version(version)
    return bool(parsed and parsed >= (5, 22, 150, 1014))


def preflight(
    installation: Installation,
    instance_ids: Iterable[str] | None = None,
    operation: str = "modify",
) -> dict[str, object]:
    """Run non-mutating checks before an operation."""

    config_path = Path(installation.config_path)
    selected_ids = list(instance_ids) if instance_ids is not None else []
    running = detect_running_processes()
    warnings: list[str] = []
    checks: list[dict[str, object]] = []
    per_instance: list[dict[str, object]] = []

    checks.append(
        {
            "name": "配置文件",
            "ok": config_path.exists(),
            "detail": str(config_path),
        }
    )
    checks.append(
        {
            "name": "写入权限",
            "ok": config_is_writable(config_path) if config_path.exists() else False,
            "detail": "文件可写" if config_is_writable(config_path) and config_path.exists() else "文件缺失或不可写",
        }
    )
    checks.append(
        {
            "name": "运行状态",
            "ok": not running,
            "detail": "未检测到运行中的 BlueStacks 进程" if not running else "检测到运行中的 BlueStacks 进程",
        }
    )

    if config_path.exists():
        try:
            store = ConfigStore.load(config_path)
            available_ids = store.instance_ids()
            if selected_ids:
                missing = [iid for iid in selected_ids if iid not in available_ids]
                if missing:
                    warnings.append(f"以下实例在配置中未找到: {', '.join(missing)}")
                for instance_id in selected_ids:
                    if instance_id in available_ids:
                        per_instance.append(
                            {
                                "instance_id": instance_id,
                                "ok": True,
                                "warnings": [],
                            }
                        )
                    else:
                        per_instance.append(
                            {
                                "instance_id": instance_id,
                                "ok": False,
                                "warnings": ["实例 ID 不存在"],
                            }
                        )
        except OSError as exc:
            warnings.append(f"配置文件读取失败: {exc}")
            checks.append({"name": "配置解析", "ok": False, "detail": str(exc)})
        else:
            checks.append({"name": "配置解析", "ok": True, "detail": "bluestacks.conf 可读取"})
    else:
        warnings.append("配置文件不存在，请选择或输入正确的 BlueStacks 安装路径。")

    if running and operation in {"root", "device", "modify"}:
        warnings.append("BlueStacks 正在运行，建议先关闭实例后再修改配置。")

    if operation == "root" and installation.version:
        if is_newer_root_patch_build(installation.version):
            warnings.append(
                "当前版本可能使用新版 guest su/完整性校验；配置文件的 Root 标志不一定代表应用内已生效，请自行验证。"
            )

    backups = list_backups(config_path)
    checks.append(
        {
            "name": "已有备份",
            "ok": bool(backups),
            "detail": f"{len(backups)} 个备份" if backups else "尚未创建备份",
        }
    )

    return {
        "config_path": str(config_path),
        "installation": installation.to_dict(),
        "operation": operation,
        "checks": checks,
        "selected_instances": per_instance,
        "running_processes": running,
        "warnings": warnings,
        "backups": backups,
        "ready": all(check.get("ok", False) for check in checks[:3]),
    }
