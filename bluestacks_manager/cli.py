"""Command-line interface for BlueStacks Manager."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .backend import ManagerBackend
from .constants import APP_NAME, APP_VERSION
from .discovery import describe_platform, discover_installations, load_instances
from .operations import random_device_for_instances, set_device, set_root
from .safety import preflight
from .backup import create_backup, list_backups, restore_backup


def _emit(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _add_config_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", "--config-path", dest="config_path", default=None, help="bluestacks.conf 路径")


def _get_backend(config_path: str | None = None, token: str | None = None) -> ManagerBackend:
    return ManagerBackend(config_path=config_path, token=token)


def cmd_discover(args: argparse.Namespace) -> int:
    backend = _get_backend(args.config_path)
    installations = backend.discover()
    _emit({"platform": describe_platform(), "installations": [item.to_dict() for item in installations]})
    return 0


def cmd_instances(args: argparse.Namespace) -> int:
    backend = _get_backend(args.config_path)
    _emit(backend.instances())
    return 0


def cmd_preflight(args: argparse.Namespace) -> int:
    backend = _get_backend(args.config_path)
    installations = backend.discover()
    installation = backend.selected_installation(installations)
    result = preflight(installation, instance_ids=args.instances, operation=args.operation)
    _emit(result)
    return 0 if result.get("ready") else 1


def cmd_root(args: argparse.Namespace) -> int:
    backend = _get_backend(args.config_path)
    installations = backend.discover()
    installation = backend.selected_installation(installations)
    result = set_root(installation.config_path, args.instances, args.enable, auto_backup=not args.no_backup)
    _emit(result.to_dict())
    return 0 if result.changed else 0


def cmd_device(args: argparse.Namespace) -> int:
    backend = _get_backend(args.config_path)
    installations = backend.discover()
    installation = backend.selected_installation(installations)
    device = {
        "profile_code": args.profile_code,
        "manufacturer": args.manufacturer,
        "brand": args.brand,
        "model": args.model,
        "width": args.width,
        "height": args.height,
        "dpi": args.dpi,
    }
    if args.random:
        result = random_device_for_instances(installation.config_path, args.instances, auto_backup=not args.no_backup)
    else:
        result = set_device(installation.config_path, args.instances, device, auto_backup=not args.no_backup)
    _emit(result.to_dict())
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    backend = _get_backend(args.config_path)
    installations = backend.discover()
    installation = backend.selected_installation(installations)
    record = create_backup(installation.config_path, note=args.note)
    _emit(record.to_dict())
    return 0


def cmd_list_backups(args: argparse.Namespace) -> int:
    backend = _get_backend(args.config_path)
    installations = backend.discover()
    installation = backend.selected_installation(installations)
    _emit(list_backups(installation.config_path))
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    backend = _get_backend(args.config_path)
    installations = backend.discover()
    installation = backend.selected_installation(installations)
    record = restore_backup(args.backup_id, installation.config_path)
    _emit(record.to_dict())
    return 0


def cmd_presets(args: argparse.Namespace) -> int:
    from .device_presets import get_presets

    _emit([preset.to_dict() for preset in get_presets()])
    return 0


def cmd_platform(args: argparse.Namespace) -> int:
    _emit(describe_platform())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME, description=f"{APP_NAME} {APP_VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover", help="检测 BlueStacks 安装与实例")
    _add_config_argument(discover)
    discover.set_defaults(func=cmd_discover)

    instances = subparsers.add_parser("instances", help="列出实例")
    _add_config_argument(instances)
    instances.set_defaults(func=cmd_instances)

    preflight_parser = subparsers.add_parser("preflight", help="修改前检查")
    _add_config_argument(preflight_parser)
    preflight_parser.add_argument("--instance", dest="instances", action="append", default=[])
    preflight_parser.add_argument("--operation", choices=["root", "device", "modify"], default="modify")
    preflight_parser.set_defaults(func=cmd_preflight)

    root = subparsers.add_parser("root", help="开启/关闭 Root")
    _add_config_argument(root)
    root.add_argument("--instance", dest="instances", action="append", required=True)
    root.add_argument("--enable", action="store_true")
    root.add_argument("--disable", action="store_true")
    root.add_argument("--no-backup", action="store_true")
    root.set_defaults(func=cmd_root)

    device = subparsers.add_parser("device", help="修改机型")
    _add_config_argument(device)
    device.add_argument("--instance", dest="instances", action="append", required=True)
    device.add_argument("--profile-code", default=None)
    device.add_argument("--manufacturer", default=None)
    device.add_argument("--brand", default=None)
    device.add_argument("--model", default=None)
    device.add_argument("--width", type=int, default=None)
    device.add_argument("--height", type=int, default=None)
    device.add_argument("--dpi", type=int, default=None)
    device.add_argument("--random", action="store_true")
    device.add_argument("--no-backup", action="store_true")
    device.set_defaults(func=cmd_device)

    backup = subparsers.add_parser("backup", help="创建备份")
    _add_config_argument(backup)
    backup.add_argument("--note", default="")
    backup.set_defaults(func=cmd_backup)

    list_backups_parser = subparsers.add_parser("backups", help="列出备份")
    _add_config_argument(list_backups_parser)
    list_backups_parser.set_defaults(func=cmd_list_backups)

    restore = subparsers.add_parser("restore", help="恢复备份")
    _add_config_argument(restore)
    restore.add_argument("backup_id", help="备份文件名")
    restore.set_defaults(func=cmd_restore)

    presets = subparsers.add_parser("presets", help="列出内置机型")
    presets.set_defaults(func=cmd_presets)

    platform_parser = subparsers.add_parser("platform", help="显示运行环境")
    platform_parser.set_defaults(func=cmd_platform)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "root":
        if args.enable == args.disable:
            parser.error("请指定 --enable 或 --disable")
        args.enable = bool(args.enable)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
