"""Detect BlueStacks installations, config files, instances, and running state."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

from .config_store import ConfigStore, instance_prefix
from .constants import (
    BLUESTACKS_PROCESS_NAMES,
    CONFIG_FILENAME,
    DEFAULT_CONFIG_CANDIDATES,
    REGISTRY_PATHS,
)
from .models import DeviceProfile, Installation, InstanceConfig


def parse_version(version: str) -> tuple[int, ...] | None:
    """Parse a dotted version string into an integer tuple, ignoring bad tails."""

    parts: list[int] = []
    for chunk in str(version).strip().split("."):
        if not chunk.isdigit():
            break
        parts.append(int(chunk))
    return tuple(parts) if parts else None


def _read_registry(path: str) -> dict[str, str]:
    """Read BlueStacks registry values on Windows."""

    if platform.system() != "Windows":
        return {}
    import winreg  # type: ignore[import-not-found]

    values: dict[str, str] = {}
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | view) as key:
                for name in ("InstallDir", "DataDir", "UserDefinedDir", "Version"):
                    try:
                        raw, _ = winreg.QueryValueEx(key, name)
                        values.setdefault(name, str(raw))
                    except FileNotFoundError:
                        pass
                    except OSError:
                        pass
        except FileNotFoundError:
            continue
        except OSError:
            continue
    return values


def _registry_installations() -> list[Installation]:
    installations: list[Installation] = []
    for source, reg_path in REGISTRY_PATHS.items():
        values = _read_registry(reg_path)
        user_dir = values.get("UserDefinedDir", "")
        data_dir = values.get("DataDir", "")
        install_dir = values.get("InstallDir", "")
        version = values.get("Version", "")
        if not user_dir or not data_dir:
            continue
        config_path = os.path.join(user_dir, CONFIG_FILENAME)
        config_exists = os.path.exists(config_path)
        instance_count = 0
        patch_mode = False
        if config_exists:
            try:
                store = ConfigStore.load(config_path)
                instance_count = len(store.instance_ids())
            except OSError:
                instance_count = 0
        parsed = parse_version(version)
        patch_mode = bool(parsed and parsed >= (5, 22, 150, 1014))
        installations.append(
            Installation(
                source=source,
                user_path=user_dir,
                data_path=data_dir,
                install_path=install_dir,
                version=version,
                config_path=config_path,
                config_exists=config_exists,
                instance_count=instance_count,
                patch_mode=patch_mode,
            )
        )
    return installations


def _explicit_installation(config_path: str | Path) -> Installation:
    path = Path(config_path).expanduser().resolve()
    parent = path.parent
    data_dir = parent.parent
    install_dir = ""
    if platform.system() == "Windows":
        install_dir = str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "BlueStacks_nxt")
    else:
        install_dir = str(parent / "engine")
    return Installation(
        source="MANUAL",
        user_path=str(parent),
        data_path=str(data_dir),
        install_path=install_dir,
        version="",
        config_path=str(path),
        config_exists=path.exists(),
        instance_count=0,
        patch_mode=False,
    )


def discover_installations(config_path: str | Path | None = None) -> list[Installation]:
    """Discover all BlueStacks installations.

    On Windows this uses registry values. On other platforms, or when an
    explicit path is supplied, the supplied path is treated as the config file.
    """

    if config_path:
        return [_explicit_installation(config_path)]
    if platform.system() == "Windows":
        installations = _registry_installations()
        # Registry values may miss a portable config; include standard paths too.
        for candidate in DEFAULT_CONFIG_CANDIDATES:
            path = Path(candidate)
            if path.exists() and not any(inst.config_path == str(path) for inst in installations):
                installations.append(_explicit_installation(path))
        return installations

    env_path = os.environ.get("BLUESTACKS_CONFIG")
    candidates: list[str] = []
    if env_path:
        candidates.append(env_path)
    candidates.extend(DEFAULT_CONFIG_CANDIDATES)
    installations = []
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            installations.append(_explicit_installation(path))
    return installations


def detect_running_processes() -> list[str]:
    """Return running BlueStacks process names."""

    if platform.system() != "Windows":
        return _detect_running_processes_unix()
    return _detect_running_processes_windows()


def _detect_running_processes_windows() -> list[str]:
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="ignore",
        )
    except OSError:
        return []
    running = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        name = line.split('","', 1)[0].strip('"')
        if name in BLUESTACKS_PROCESS_NAMES:
            running.add(name)
    return sorted(running)


def _detect_running_processes_unix() -> list[str]:
    try:
        result = subprocess.run(
            ["ps", "-eo", "comm="],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    running = set()
    for line in result.stdout.splitlines():
        name = Path(line.strip()).name.lower()
        if any(process.lower().removesuffix(".exe") == name for process in BLUESTACKS_PROCESS_NAMES):
            running.add(name)
    return sorted(running)


def load_instances(installation: Installation) -> list[InstanceConfig]:
    """Load all instances from an installation's config file."""

    if not installation.config_exists:
        return []
    try:
        store = ConfigStore.load(installation.config_path)
    except OSError:
        return []
    running = set(detect_running_processes())
    instances: list[InstanceConfig] = []
    for instance_id in store.instance_ids():
        device = {
            "profile_code": store.instance_value(instance_id, "device_profile_code"),
            "brand": store.instance_value(instance_id, "device_custom_brand"),
            "manufacturer": store.instance_value(instance_id, "device_custom_manufacturer"),
            "model": store.instance_value(instance_id, "device_custom_model"),
            "width": int(store.instance_value(instance_id, "fb_width") or 0),
            "height": int(store.instance_value(instance_id, "fb_height") or 0),
            "dpi": int(store.instance_value(instance_id, "dpi") or 0),
        }
        warnings: list[str] = []
        if running:
            warnings.append("BlueStacks 正在运行，修改前建议先关闭实例。")
        instance_dir = os.path.join(installation.data_path, "Engine", instance_id)
        device_profile = DeviceProfile(
            profile_code=device["profile_code"],
            brand=device["brand"],
            manufacturer=device["manufacturer"],
            model=device["model"],
            width=device["width"],
            height=device["height"],
            dpi=device["dpi"],
        )
        instances.append(
            InstanceConfig(
                instance_id=instance_id,
                display_name=store.instance_value(instance_id, "display_name") or instance_id,
                config_path=installation.config_path,
                root_enabled=store.instance_value(instance_id, "enable_root_access") == "1",
                device=device_profile,
                width=device["width"],
                height=device["height"],
                dpi=device["dpi"],
                adb_port=store.instance_value(instance_id, "status.adb_port") or store.instance_value(instance_id, "adb_port"),
                instance_dir=instance_dir,
                warnings=warnings,
            )
        )
    return instances


def instance_dir_for(installation: Installation, instance_id: str) -> str:
    return os.path.join(installation.data_path, "Engine", instance_id)


def config_is_writable(config_path: str | Path) -> bool:
    path = Path(config_path)
    if not path.exists():
        return False
    return os.access(path, os.W_OK)


def describe_platform() -> dict[str, Any]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "bluestacks_processes": detect_running_processes(),
    }


def iter_instance_keys(store: ConfigStore, instance_id: str) -> Iterable[str]:
    prefix = instance_prefix(instance_id)
    return (key for key in store.keys if key.startswith(prefix))
