"""Built-in device profiles and known BlueStacks profile codes.

Profile codes are internal BlueStacks identifiers. Newer builds may change the
available list, so the UI always allows manual entry. ``custom`` is used as a
stable marker for profiles created from brand/manufacturer/model fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class DevicePreset:
    """A user-friendly device profile."""

    label: str
    code: str
    manufacturer: str
    brand: str
    model: str
    width: int
    height: int
    dpi: int = 240
    custom: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "code": self.code,
            "manufacturer": self.manufacturer,
            "brand": self.brand,
            "model": self.model,
            "width": self.width,
            "height": self.height,
            "dpi": self.dpi,
            "custom": self.custom,
        }


# Known profile codes seen in public BlueStacks configuration samples. Labels
# are for convenience; BlueStacks versions can expose different profiles.
PROFILE_CODES: list[tuple[str, str]] = [
    ("snpe", "Samsung / Snapdragon profile"),
    ("sttu", "Samsung profile"),
    ("optr", "OnePlus / Oppo profile"),
    ("custom", "自定义机型"),
]

DEVICE_PRESETS: list[DevicePreset] = [
    DevicePreset("Samsung Galaxy S8", "snpe", "samsung", "Samsung", "Galaxy S8", 1440, 2960),
    DevicePreset("Samsung Galaxy S10", "optr", "samsung", "Samsung", "Galaxy S10", 1440, 3040),
    DevicePreset("Samsung Galaxy S20 Ultra", "sttu", "samsung", "Samsung", "Galaxy S20 Ultra", 1440, 3200),
    DevicePreset("OnePlus 3T", "optr", "oneplus", "OnePlus", "3T", 1280, 1920),
    DevicePreset("OnePlus 5", "optr", "oneplus", "OnePlus", "5", 1080, 1920),
    DevicePreset("Google Pixel 2 XL", "snpe", "google", "Google", "Pixel 2 XL", 1440, 2720),
    DevicePreset("ASUS ROG 2", "sttu", "asus", "ASUS", "ROG Phone 2", 1080, 2340),
    DevicePreset("LG V30", "optr", "lg", "LG", "V30", 1440, 2880),
    DevicePreset("Xiaomi Mi 11", "snpe", "xiaomi", "Xiaomi", "Mi 11", 1440, 3200),
    DevicePreset("自定义机型", "custom", "", "", "", 1080, 2400, custom=True),
]


def get_presets() -> list[DevicePreset]:
    return list(DEVICE_PRESETS)


def get_profile_codes() -> list[tuple[str, str]]:
    return list(PROFILE_CODES)


def find_preset(code: str) -> DevicePreset | None:
    for preset in DEVICE_PRESETS:
        if preset.code == code:
            return preset
    return None


def preset_to_device(preset: DevicePreset, overrides: dict[str, object] | None = None) -> dict[str, object]:
    """Convert a preset to a device dict, applying optional overrides."""

    device = preset.to_dict()
    if overrides:
        device.update({key: value for key, value in overrides.items() if value not in (None, "")})
    return device


def is_valid_profile_code(code: str, allowed: Iterable[str] | None = None) -> bool:
    allowed_set = set(allowed or (code for code, _ in PROFILE_CODES))
    return code in allowed_set
