# 蓝叠国际版管理器

一个面向 Windows 的 BlueStacks 5 本地管理工具。它使用现代化卡片界面、绿色主题、暗色/亮色切换，并提供实例检测、Root 开关、机型修改、随机机型、备份恢复和修改前检查。

## 功能

- 自动检测 BlueStacks 5 安装位置和 `bluestacks.conf`
  - Windows：读取 `HKLM\SOFTWARE\BlueStacks_nxt`、MSI、CN 注册表分支
  - 支持手动指定 portable/demo 配置文件路径
- 自动列出所有实例及其显示名、Root 状态、ADB 端口、分辨率、DPI 和实例目录
- 一键开启/关闭实例 Root
  - 写入 `bst.instance.<id>.enable_root_access`
  - 每次修改前自动备份
  - 对新版 BlueStacks 显示兼容性警告，避免把“配置已开启”误解释为“应用内一定已 Root”
- 修改机型
  - 支持 `device_profile_code`、`device_custom_manufacturer`、`device_custom_brand`、`device_custom_model`
  - 内置常见 Profile Code 和机型预设
  - 支持手动填写 manufacturer/brand/model/width/height/dpi
  - 支持随机自动生成
- 批量操作
  - 多选实例后批量开启/关闭 Root
  - 多选实例后批量应用同一机型或随机机型
- 配置安全
  - 修改前检查配置文件、写入权限、运行中的 BlueStacks 进程
  - 检测到运行中实例时给出警告
  - 原子写入，避免直接覆盖导致配置损坏
  - 自动备份和恢复
- 其他
  - 本地 HTTP API + 本地静态 UI，不把数据发送到远端
  - 首次运行可设置本地访问令牌
  - 操作历史记录
  - 提供 CLI 便于脚本化
  - Linux/macOS 可运行演示配置，方便预览 UI

## 界面

界面是本地 Web UI，使用现代卡片布局和绿色视觉主题：

- 概览：实例数量、Root 数量、运行状态、备份数量、安装信息
- 实例：卡片列表、批量选择、Root 开关、机型入口
- 机型：表单编辑、内置预设、随机生成
- 检查：修改前检查、警告列表
- 备份：创建、恢复、删除
- 设置：令牌、配置文件路径、运行环境、操作记录

界面不使用 emoji，使用矢量图标。

## 快速开始

### Windows

1. 安装 Python 3.10+
2. 安装依赖：

```powershell
python -m pip install -e .
```

3. 运行桌面界面：

```powershell
bluestacks-manager-gui
```

或使用提供的 EXE（见 Releases）。

4. 也可以只运行本地服务并打开浏览器：

```powershell
bluestacks-manager-gui --serve --browser
```

### Linux / macOS 演示

```bash
python -m pip install pywebview
python scripts/run_linux_demo.py
```

或：

```bash
python -m bluestacks_manager.app --demo --serve --browser --host 0.0.0.0
```

演示模式使用临时配置文件，不修改真实 BlueStacks 安装。

## CLI

```bash
# 检测安装与实例
bluestacks-manager discover

# 列出实例
bluestacks-manager instances

# 修改前检查
bluestacks-manager preflight --instance Rvc64 --operation root

# 开启 Root
bluestacks-manager root --instance Rvc64 --enable

# 关闭 Root
bluestacks-manager root --instance Rvc64 --disable

# 修改机型
bluestacks-manager device --instance Rvc64 --profile-code custom --manufacturer samsung --brand Samsung --model "Galaxy S23" --width 1080 --height 2400 --dpi 240

# 随机机型
bluestacks-manager device --instance Rvc64 --random

# 备份
bluestacks-manager backup --note "before changes"

# 列出备份
bluestacks-manager backups

# 恢复备份
bluestacks-manager restore bluestacks.conf.20260101-000000.bak

# 内置机型
bluestacks-manager presets
```

常用参数：

```text
--config-path / --config    指定 bluestacks.conf
--host                      本地 API 地址
--port                      本地 API 端口
--token                     本地访问令牌
--demo                      演示配置
--serve                     只启动服务
--browser                   使用系统浏览器
```

## 本地 API

界面通过本机 HTTP API 操作。默认仅监听本机，首次运行建议设置令牌。主要接口：

```text
GET  /api/health
GET  /api/state
GET  /api/installations
GET  /api/instances
GET  /api/presets
GET  /api/profile-codes
GET  /api/preflight
GET  /api/backups
POST /api/root
POST /api/device
POST /api/device/random
POST /api/backup
POST /api/backup/<id>/restore
POST /api/backup/<id>/delete
POST /api/process/stop
```

除 `/api/health` 外，API 请求需携带 `X-Manager-Token` 头。

## 打包 Windows EXE

仓库包含 GitHub Actions 工作流：`.github/workflows/build-windows.yml`。

推送到 `main` 后，工作流会：

1. 在 `windows-latest` 上安装 Python、PyInstaller 和 pywebview
2. 打包单文件 EXE
3. 复制为 `BlueStacksManager.exe` 和 `蓝叠国际版管理器.exe`
4. 上传构建产物并创建/更新 GitHub Release

本地打包：

```powershell
python -m pip install pyinstaller pywebview
pyinstaller --noconfirm --clean --onefile --windowed --name BlueStacksManager `
  --icon assets/icon.ico `
  --add-data "bluestacks_manager/assets;bluestacks_manager/assets" `
  --hidden-import pywebview `
  --hidden-import pywebview.gui `
  --collect-submodules pywebview `
  --collect-data pywebview `
  run_gui.py
```

## 安全说明

- 修改 BlueStacks 配置前建议关闭实例。工具会在检测到运行中 BlueStacks 进程时警告。
- Root 支持取决于 BlueStacks 版本。5.22.150.1014 及后续版本可能使用新版 guest su/完整性校验，需要额外补丁或兼容性验证。
- “已写入 Root 配置”不等于“所有应用内都已获得 Root 权限”。请自行使用需要 Root 的应用验证。
- 修改机型主要用于兼容部分应用/游戏的设备识别。不同 BlueStacks 版本支持的 Profile Code 可能不同。
- 本工具不会上传配置、机型或令牌。界面和 API 仅运行在本机。

## 目录结构

```text
bluestacks_manager/
  backend.py          本地 HTTP API 与静态资源服务
  config_store.py     安全读写 bluestacks.conf
  discovery.py        注册表/路径/实例检测
  device_presets.py   内置机型与 Profile Code
  random_device.py    随机机型生成
  operations.py       Root/机型/批量操作
  safety.py           修改前检查
  backup.py           备份恢复
  app.py              桌面入口
  cli.py              命令行入口
bluestacks_manager/assets/
  index.html          UI 结构
  app.css             绿色主题与暗色/亮色样式
  app.js              UI 逻辑
  icons.svg           矢量图标
  icon.svg/png/ico    应用图标
tests/                自动化测试
scripts/              Linux 演示脚本
.github/workflows/    Windows EXE 构建
```

## 开发与测试

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
```

## 许可证

MIT License。

## 免责声明

BlueStacks 是 BlueStacks Inc. 的产品。本项目为独立开源工具，不修改、不分发、也不逆向 BlueStacks 安装程序。使用 Root、机型修改或补丁功能时，请遵守 BlueStacks 服务条款和当地法律。作者不对特定版本兼容性、游戏封禁或数据损失负责。
