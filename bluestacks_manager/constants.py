"""Shared constants and low-level field mappings."""

from __future__ import annotations

APP_NAME = "蓝叠国际版管理器"
APP_VERSION = "1.0.0"
APP_ID = "com.elysianki4225.bluestacks-manager"
CONFIG_FILENAME = "bluestacks.conf"
BACKUP_DIR_NAME = "bluestacks-manager-backups"
BACKUP_PREFIX = "bluestacks.conf"

# Default BlueStacks 5 installation roots. Registry values remain the primary
# source on Windows; these paths are fallbacks for portable/explicit configs.
DEFAULT_CONFIG_CANDIDATES = [
    "C:/ProgramData/BlueStacks_nxt/bluestacks.conf",
    "C:/ProgramData/BlueStacks_msi5/bluestacks.conf",
    "C:/Program Files/BlueStacks_nxt/bluestacks.conf",
    "/opt/bluestacks_nxt/bluestacks.conf",
    "/mnt/c/ProgramData/BlueStacks_nxt/bluestacks.conf",
]

REGISTRY_PATHS = {
    "NXT": "SOFTWARE\\BlueStacks_nxt",
    "MSI": "SOFTWARE\\BlueStacks_msi5",
    "CN": "SOFTWARE\\BlueStacks_nxt_cn",
}

# BlueStacks process names that can lock the config or engine files.
BLUESTACKS_PROCESS_NAMES = {
    "HD-Player.exe",
    "HD-MultiInstanceManager.exe",
    "BlueStacks.exe",
    "HD-Agent.exe",
    "BstkSVC.exe",
    "HD-Frontend.exe",
    "HD-LogRotatorService.exe",
    "BlueStacksWebHelper.exe",
    "HD-ADB.exe",
}

# Instance-level configuration suffixes used by this manager.
ROOT_FIELD = "enable_root_access"
DISPLAY_NAME_FIELD = "display_name"
PROFILE_CODE_FIELD = "device_profile_code"
BRAND_FIELD = "device_custom_brand"
MANUFACTURER_FIELD = "device_custom_manufacturer"
MODEL_FIELD = "device_custom_model"
WIDTH_FIELD = "fb_width"
HEIGHT_FIELD = "fb_height"
DPI_FIELD = "dpi"
ADB_PORT_FIELD = "adb_port"
STATUS_ADB_PORT_FIELD = "status.adb_port"

# Root access compatibility threshold. Newer builds may use signed guest su and
# integrity checks, so a config flag is not always equivalent to verified root.
PATCH_MIN_VERSION = (5, 22, 150, 1014)

API_TOKEN_ENV = "BLUESTACKS_MANAGER_TOKEN"
DEFAULT_PORT = 8765
