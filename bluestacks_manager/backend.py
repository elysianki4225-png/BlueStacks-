"""Local HTTP API and static asset server for the manager UI."""

from __future__ import annotations

import json
import os
import secrets
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from . import __version__
from .constants import API_TOKEN_ENV, APP_ID, APP_NAME, APP_VERSION, DEFAULT_PORT
from .device_presets import get_presets, get_profile_codes
from .discovery import describe_platform, discover_installations, load_instances
from .models import Installation
from .operations import random_device_for_instances, set_device, set_root, stop_bluestacks_processes
from .random_device import generate_device
from .safety import preflight, resolve_backup
from .backup import create_backup, delete_backup, list_backups, restore_backup

ASSETS_DIR = Path(__file__).resolve().parent / "assets"


class ManagerBackend:
    """Application state and API methods."""

    def __init__(self, config_path: str | os.PathLike[str] | None = None, token: str | None = None) -> None:
        self._lock = threading.RLock()
        self.config_path = str(config_path) if config_path else None
        self.token = token or os.environ.get(API_TOKEN_ENV) or secrets.token_urlsafe(24)
        self.demo = bool(os.environ.get("BLUESTACKS_MANAGER_DEMO"))
        self.history: list[dict[str, Any]] = []
        self._installation_cache: list[Installation] = []

    def set_token(self, token: str) -> None:
        token = token.strip()
        if not token:
            raise ValueError("访问令牌不能为空")
        with self._lock:
            self.token = token

    def token_configured(self) -> bool:
        return bool(self.token)

    def auth_header(self) -> dict[str, str]:
        return {"X-Manager-Token": self.token}

    def authenticate(self, token: str | None) -> bool:
        if not self.token:
            return False
        return bool(token) and secrets.compare_digest(token, self.token)

    def record_history(self, action: str, summary: dict[str, Any]) -> None:
        entry = {"action": action, "summary": summary}
        self.history.append(entry)
        del self.history[:-200]

    def discover(self) -> list[Installation]:
        if self.config_path:
            return discover_installations(self.config_path)
        return discover_installations()

    def selected_installation(self, installations: list[Installation]) -> Installation:
        if not installations:
            raise FileNotFoundError("未检测到 BlueStacks 安装或配置文件")
        if len(installations) == 1:
            return installations[0]
        if self.config_path:
            for installation in installations:
                if installation.config_path == os.path.normpath(self.config_path):
                    return installation
        return installations[0]

    def instances(self) -> list[dict[str, Any]]:
        installations = self.discover()
        installation = self.selected_installation(installations)
        return [item.to_dict() for item in load_instances(installation)]

    def state(self) -> dict[str, Any]:
        return {
            "app_name": APP_NAME,
            "app_id": APP_ID,
            "version": APP_VERSION,
            "demo": self.demo,
            "platform": describe_platform(),
            "config_path": self.config_path,
            "token_configured": self.token_configured(),
            "installation_count": len(self.discover()),
            "history": list(self.history),
        }

    def get_presets(self) -> list[dict[str, Any]]:
        return [preset.to_dict() for preset in get_presets()]

    def get_profile_codes(self) -> list[dict[str, str]]:
        return [{"code": code, "label": label} for code, label in get_profile_codes()]

    def do_preflight(self, config_path: str | None = None, instance_ids: list[str] | None = None, operation: str = "modify") -> dict[str, Any]:
        installations = self.discover()
        installation = self.selected_installation(installations)
        if config_path:
            installation = Installation(
                source="MANUAL",
                user_path=str(Path(config_path).expanduser().parent),
                data_path=str(Path(config_path).expanduser().parent.parent),
                install_path="",
                version="",
                config_path=str(Path(config_path).expanduser()),
                config_exists=Path(config_path).exists(),
                instance_count=0,
                patch_mode=False,
            )
        return preflight(installation, instance_ids=instance_ids or [], operation=operation)

    def backups(self, config_path: str | None = None) -> list[dict[str, Any]]:
        installations = self.discover()
        installation = self.selected_installation(installations)
        path = config_path or installation.config_path
        return list_backups(path)

    def make_backup(self, config_path: str | None = None, note: str = "") -> dict[str, Any]:
        installations = self.discover()
        installation = self.selected_installation(installations)
        path = config_path or installation.config_path
        record = create_backup(path, note=note)
        self.record_history("backup", {"path": path, "backup_id": record.backup_id})
        return record.to_dict()

    def restore(self, backup_id: str, config_path: str | None = None) -> dict[str, Any]:
        installations = self.discover()
        installation = self.selected_installation(installations)
        path = config_path or installation.config_path
        record = restore_backup(backup_id, path)
        self.record_history("restore", {"path": path, "backup_id": backup_id})
        return record.to_dict()

    def delete_backup(self, backup_id: str, config_path: str | None = None) -> dict[str, Any]:
        installations = self.discover()
        installation = self.selected_installation(installations)
        path = config_path or installation.config_path
        delete_backup(backup_id, path)
        self.record_history("delete_backup", {"path": path, "backup_id": backup_id})
        return {"deleted": True, "backup_id": backup_id}

    def set_root(self, instance_ids: list[str], enabled: bool, config_path: str | None = None, auto_backup: bool = True) -> dict[str, Any]:
        installations = self.discover()
        installation = self.selected_installation(installations)
        path = config_path or installation.config_path
        result = set_root(path, instance_ids, enabled, auto_backup=auto_backup)
        self.record_history("root", {"instance_ids": instance_ids, "enabled": enabled, "path": path})
        return result.to_dict()

    def set_device(self, instance_ids: list[str], device: dict[str, Any], config_path: str | None = None, auto_backup: bool = True) -> dict[str, Any]:
        installations = self.discover()
        installation = self.selected_installation(installations)
        path = config_path or installation.config_path
        result = set_device(path, instance_ids, device, auto_backup=auto_backup)
        self.record_history("device", {"instance_ids": instance_ids, "device": device, "path": path})
        return result.to_dict()

    def random_preview(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        """Generate a random device profile without writing it."""

        return generate_device(
            manufacturer=overrides.get("manufacturer") or None if overrides else None,
            brand=overrides.get("brand") or None if overrides else None,
            model=overrides.get("model") or None if overrides else None,
            profile_code=overrides.get("profile_code") or None if overrides else None,
        )

    def random_device(self, instance_ids: list[str], config_path: str | None = None, overrides: dict[str, Any] | None = None, auto_backup: bool = True) -> dict[str, Any]:
        overrides = overrides or {}
        installations = self.discover()
        installation = self.selected_installation(installations)
        path = config_path or installation.config_path
        result = random_device_for_instances(
            path,
            instance_ids,
            manufacturer=overrides.get("manufacturer") or None,
            brand=overrides.get("brand") or None,
            model=overrides.get("model") or None,
            profile_code=overrides.get("profile_code") or None,
            auto_backup=auto_backup,
        )
        self.record_history("random_device", {"instance_ids": instance_ids, "path": path})
        return result.to_dict()

    def stop_processes(self, force: bool = False) -> dict[str, Any]:
        stopped = stop_bluestacks_processes(force=force)
        self.record_history("stop", {"stopped": stopped, "force": force})
        return {"stopped": stopped, "force": force}


class ManagerRequestHandler(SimpleHTTPRequestHandler):
    """Serve bundled UI assets and the local JSON API."""

    backend: ManagerBackend | None = None
    server_version = "BlueStacksManager/" + APP_VERSION

    def __init__(self, *args: Any, backend: ManagerBackend | None = None, **kwargs: Any) -> None:
        self.backend = backend or self.__class__.backend
        if self.backend is None:
            raise RuntimeError("Backend is not configured")
        super().__init__(*args, directory=str(ASSETS_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        # Keep the desktop window quiet; logs are available through the CLI.
        if os.environ.get("BLUESTACKS_MANAGER_HTTP_LOG"):
            super().log_message(format, *args)

    def end_headers(self) -> None:
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Manager-Token")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed)
        else:
            super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_post(parsed)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _send_json(self, data: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        self._send_json({"ok": False, "error": message}, status)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        try:
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8")) if raw.strip() else {}
            if not isinstance(data, dict):
                raise ValueError("请求体必须是 JSON 对象")
            return data
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"请求体解析失败: {exc}")

    def _require_auth(self) -> bool:
        token = self.headers.get("X-Manager-Token") or parse_qs(urlparse(self.path).query).get("token", [""])[0]
        if not self.backend.authenticate(token):
            self._error("访问令牌无效", HTTPStatus.UNAUTHORIZED)
            return False
        return True

    def handle_api_get(self, parsed: Any) -> None:
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/api/health":
            self._send_json({"ok": True, "service": APP_NAME, "version": APP_VERSION})
            return
        if path == "/api/token/status":
            self._send_json({"configured": self.backend.token_configured()})
            return
        if path == "/api/state":
            if not self._require_auth():
                return
            self._send_json({"ok": True, "data": self.backend.state()})
            return
        if path == "/api/installations":
            if not self._require_auth():
                return
            installations = self.backend.discover()
            self._send_json({"ok": True, "data": [item.to_dict() for item in installations]})
            return
        if path == "/api/instances":
            if not self._require_auth():
                return
            config_path = query.get("config_path", [None])[0]
            if config_path:
                self.backend.config_path = config_path
            self._send_json({"ok": True, "data": self.backend.instances()})
            return
        if path == "/api/presets":
            if not self._require_auth():
                return
            self._send_json({"ok": True, "data": self.backend.get_presets()})
            return
        if path == "/api/profile-codes":
            if not self._require_auth():
                return
            self._send_json({"ok": True, "data": self.backend.get_profile_codes()})
            return
        if path == "/api/preflight":
            if not self._require_auth():
                return
            instance_ids = [value for values in query.get("instance_ids", []) for value in values]
            operation = query.get("operation", ["modify"])[0]
            config_path = query.get("config_path", [None])[0]
            self._send_json({"ok": True, "data": self.backend.do_preflight(config_path, instance_ids, operation)})
            return
        if path == "/api/backups":
            if not self._require_auth():
                return
            config_path = query.get("config_path", [None])[0]
            self._send_json({"ok": True, "data": self.backend.backups(config_path)})
            return
        self._error("接口不存在", HTTPStatus.NOT_FOUND)

    def handle_api_post(self, parsed: Any) -> None:
        path = parsed.path
        try:
            body = self._read_json()
        except ValueError as exc:
            self._error(str(exc))
            return

        if path == "/api/token":
            # Allow first-run token setup from the local UI. In demo mode the
            # token can be replaced so browser previews work without pywebview.
            if self.backend.token_configured() and not self.backend.demo:
                self._error("访问令牌已配置，无法通过 HTTP 重置", HTTPStatus.FORBIDDEN)
                return
            token = str(body.get("token", "")).strip()
            if not token:
                self._error("请填写访问令牌")
                return
            self.backend.set_token(token)
            self._send_json({"ok": True, "configured": True})
            return
        if not self._require_auth():
            return

        if path == "/api/installation":
            config_path = str(body.get("config_path", "")).strip()
            if not config_path:
                self._error("请输入配置文件路径")
                return
            self.backend.config_path = config_path
            self._send_json({"ok": True, "data": self.backend.state()})
            return
        if path == "/api/backup":
            try:
                self._send_json({"ok": True, "data": self.backend.make_backup(body.get("config_path"), str(body.get("note", "")))})
            except OSError as exc:
                self._error(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if path.startswith("/api/backup/") and path.endswith("/restore"):
            backup_id = path.split("/")[2]
            try:
                self._send_json({"ok": True, "data": self.backend.restore(backup_id, body.get("config_path"))})
            except (ValueError, FileNotFoundError, OSError) as exc:
                self._error(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if path.startswith("/api/backup/") and path.endswith("/delete"):
            backup_id = path.split("/")[2]
            try:
                self._send_json({"ok": True, "data": self.backend.delete_backup(backup_id, body.get("config_path"))})
            except (ValueError, FileNotFoundError, OSError) as exc:
                self._error(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if path == "/api/root":
            instance_ids = list(body.get("instance_ids", []))
            if not instance_ids:
                self._error("请选择至少一个实例")
                return
            enabled = bool(body.get("enabled", False))
            try:
                self._send_json({"ok": True, "data": self.backend.set_root(instance_ids, enabled, body.get("config_path"), bool(body.get("auto_backup", True)))})
            except (ValueError, FileNotFoundError, OSError) as exc:
                self._error(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if path == "/api/device":
            instance_ids = list(body.get("instance_ids", []))
            device = dict(body.get("device", {}))
            if not instance_ids:
                self._error("请选择至少一个实例")
                return
            if not device:
                self._error("请提供机型信息")
                return
            try:
                self._send_json({"ok": True, "data": self.backend.set_device(instance_ids, device, body.get("config_path"), bool(body.get("auto_backup", True)))})
            except (ValueError, FileNotFoundError, OSError) as exc:
                self._error(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if path == "/api/device/preview":
            overrides = dict(body.get("overrides", {}))
            self._send_json({"ok": True, "data": self.backend.random_preview(overrides)})
            return
        if path == "/api/device/random":
            instance_ids = list(body.get("instance_ids", []))
            if not instance_ids:
                self._error("请选择至少一个实例")
                return
            try:
                self._send_json({"ok": True, "data": self.backend.random_device(instance_ids, body.get("config_path"), dict(body.get("overrides", {})), bool(body.get("auto_backup", True)))})
            except (ValueError, FileNotFoundError, OSError) as exc:
                self._error(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if path == "/api/process/stop":
            try:
                self._send_json({"ok": True, "data": self.backend.stop_processes(bool(body.get("force", False)))})
            except OSError as exc:
                self._error(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self._error("接口不存在", HTTPStatus.NOT_FOUND)


def create_server(
    *,
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    config_path: str | os.PathLike[str] | None = None,
    token: str | None = None,
) -> tuple[ThreadingHTTPServer, ManagerBackend]:
    """Create and start a local HTTP server in a background thread."""

    backend = ManagerBackend(config_path=config_path, token=token)

    class Handler(ManagerRequestHandler):
        pass

    Handler.backend = backend
    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, name="bluestacks-manager-http", daemon=True)
    thread.start()
    return server, backend


def create_demo_server(*, port: int = DEFAULT_PORT, temp_config: bool = True) -> tuple[ThreadingHTTPServer, ManagerBackend, Path | None]:
    """Create a server with a temporary demo BlueStacks config."""

    demo_path: Path | None = None
    if temp_config:
        demo_path = Path.home() / ".bluestacks-manager-demo" / "bluestacks.conf"
        demo_path.parent.mkdir(parents=True, exist_ok=True)
        demo_path.write_text(
            "\n".join(
                [
                    'bst.instance.Rvc64.display_name="BlueStacks 5"',
                    'bst.instance.Rvc64.enable_root_access="0"',
                    'bst.instance.Rvc64.device_profile_code="sttu"',
                    'bst.instance.Rvc64.device_custom_brand=""',
                    'bst.instance.Rvc64.device_custom_manufacturer=""',
                    'bst.instance.Rvc64.device_custom_model=""',
                    'bst.instance.Rvc64.fb_width="1080"',
                    'bst.instance.Rvc64.fb_height="2400"',
                    'bst.instance.Rvc64.dpi="240"',
                    'bst.instance.Rvc64.status.adb_port="5555"',
                    '',
                    'bst.instance.Pie64_1.display_name="BlueStacks 1"',
                    'bst.instance.Pie64_1.enable_root_access="1"',
                    'bst.instance.Pie64_1.device_profile_code="snpe"',
                    'bst.instance.Pie64_1.device_custom_brand="Samsung"',
                    'bst.instance.Pie64_1.device_custom_manufacturer="samsung"',
                    'bst.instance.Pie64_1.device_custom_model="Galaxy S8"',
                    'bst.instance.Pie64_1.fb_width="1440"',
                    'bst.instance.Pie64_1.fb_height="2960"',
                    'bst.instance.Pie64_1.dpi="240"',
                    'bst.instance.Pie64_1.status.adb_port="5565"',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    server, backend = create_server(host="0.0.0.0", port=port, config_path=demo_path)
    backend.demo = True
    return server, backend, demo_path
