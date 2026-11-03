"""Desktop entry point: local HTTP API + pywebview shell."""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path
from typing import Any

from .backend import create_demo_server, create_server
from .constants import API_TOKEN_ENV, APP_NAME, APP_VERSION, DEFAULT_PORT


def _pywebview_api(backend: Any) -> Any:
    try:
        import pywebview  # type: ignore[import-not-found]
    except Exception:
        return None

    class ManagerAPI:
        def get_token(self) -> str:
            return backend.token

        def get_app_info(self) -> dict[str, str]:
            return {"name": APP_NAME, "version": APP_VERSION}

        def get_config_path(self) -> str:
            return backend.config_path or ""

    return ManagerAPI()


def _open_pywebview(url: str, backend: Any) -> bool:
    try:
        import pywebview  # type: ignore[import-not-found]
    except Exception:
        return False
    api = _pywebview_api(backend)
    if api is not None:
        pywebview.create_window(APP_NAME, url, js_api=api, width=1280, height=840)
    else:
        pywebview.create_window(APP_NAME, url, width=1280, height=840)
    pywebview.start()
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="蓝叠国际版管理器", description="蓝叠国际版管理器")
    parser.add_argument("--host", default="127.0.0.1", help="本地 API 地址（GUI 默认仅本机）")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="本地 API 端口")
    parser.add_argument("--config-path", default=os.environ.get("BLUESTACKS_CONFIG"), help="BlueStacks bluestacks.conf 路径")
    parser.add_argument("--token", default=os.environ.get(API_TOKEN_ENV), help="本地访问令牌")
    parser.add_argument("--demo", action="store_true", help="使用临时演示配置")
    parser.add_argument("--serve", action="store_true", help="只启动本地服务，不打开桌面窗口")
    parser.add_argument("--browser", action="store_true", help="使用系统浏览器而不是 pywebview")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    args = parser.parse_args(argv)

    demo = bool(args.demo or os.environ.get("BLUESTACKS_MANAGER_DEMO"))
    if demo:
        server, backend, demo_path = create_demo_server(port=args.port)
        config_path = str(demo_path) if demo_path else ""
    else:
        server, backend = create_server(host=args.host, port=args.port, config_path=args.config_path, token=args.token)
        config_path = args.config_path or ""

    host, port = server.server_address[0], server.server_address[1]
    url = f"http://{host}:{port}/"
    print(f"{APP_NAME} {APP_VERSION}")
    print(f"本地服务: {url}")
    if config_path:
        print(f"配置文件: {config_path}")
    print(f"访问令牌: {backend.token}")

    if args.serve:
        try:
            while True:
                server.handle_request()
        except KeyboardInterrupt:
            print("\n已停止本地服务。")
        return 0

    if args.browser:
        webbrowser.open(url)
        print("已使用系统浏览器打开界面。")
    else:
        opened = _open_pywebview(url, backend)
        if not opened:
            webbrowser.open(url)
            print("pywebview 不可用，已使用系统浏览器打开界面。")
        try:
            while True:
                server.handle_request()
        except KeyboardInterrupt:
            print("\n已停止本地服务。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
