"""Random device-profile generation.

The generator intentionally creates plausible Android device identities from
local word lists. It does not claim to create devices supported by any specific
BlueStacks build; users should verify app compatibility after applying changes.
"""

from __future__ import annotations

import random
import secrets
from typing import Literal

from .device_presets import DevicePreset

MANUFACTURERS = [
    "Samsung",
    "Xiaomi",
    "OnePlus",
    "Google",
    "Motorola",
    "ASUS",
    "OPPO",
    "Realme",
    "vivo",
    "Nothing",
    "Sony",
    "HTC",
    "LG",
    "Nokia",
]

BRAND_TEMPLATES = [
    "{manufacturer} {series}",
    "{manufacturer} {series} Pro",
    "{manufacturer} {series} Ultra",
    "{manufacturer} {series} Lite",
    "{manufacturer} {series} Max",
    "{manufacturer} {series} Neo",
]

SERIES = [
    "Galaxy S",
    "Galaxy A",
    "Mi",
    "Redmi",
    "Note",
    "Turbo",
    "Fold",
    "Pixel",
    "Xperia",
    "ROG Phone",
    "Edge",
    "Velvet",
    "Desire",
    "Nord",
]

MODEL_SUFFIXES = ["", "1", "2", "3", "5", "6", "7", "8", "9", "10", "11", "12", "Pro", "Ultra", "Lite"]

RESOLUTIONS = [
    (1080, 1920),
    (1080, 2340),
    (1080, 2400),
    (1440, 2560),
    (1440, 2960),
    (1440, 3040),
    (1440, 3200),
    (720, 1280),
    (800, 1280),
    (720, 1440),
]

DPIS = [160, 240, 275, 320, 400, 440, 480, 560]

PROFILE_CODE_CHOICES = ["snpe", "sttu", "optr", "custom"]


def _random_series() -> str:
    return random.choice(SERIES)


def _random_brand(manufacturer: str) -> str:
    template = random.choice(BRAND_TEMPLATES)
    series = _random_series()
    brand = template.format(manufacturer=manufacturer, series=series)
    # Normalize common spacing/case without making the result look mechanical.
    brand = brand.replace("  ", " ").strip()
    return brand


def _random_model(manufacturer: str, brand: str) -> str:
    # Use a short alnum token plus common model suffix for stable readability.
    root = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(5))
    suffix = random.choice(MODEL_SUFFIXES)
    prefix = "".join(word[0] for word in brand.split())[:2].upper()
    return f"{prefix}{root}{suffix}"


def generate_device(
    *,
    manufacturer: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    width: int | None = None,
    height: int | None = None,
    dpi: int | None = None,
    profile_code: str | None = None,
) -> dict[str, object]:
    """Generate a random device dict.

    Any argument provided by the caller overrides the generated value, making
    the function usable for “randomize one field only” flows.
    """

    manufacturer = manufacturer or random.choice(MANUFACTURERS)
    brand = brand or _random_brand(manufacturer)
    model = model or _random_model(manufacturer, brand)
    resolution = random.choice(RESOLUTIONS)
    device_width, device_height = resolution
    device_dpi = random.choice(DPIS)
    code = profile_code or random.choice(PROFILE_CODE_CHOICES)
    return {
        "profile_code": code,
        "manufacturer": manufacturer,
        "brand": brand,
        "model": model,
        "width": width if width is not None else device_width,
        "height": height if height is not None else device_height,
        "dpi": dpi if dpi is not None else device_dpi,
    }


def random_preset() -> DevicePreset:
    preset = random.choice(DEVICE_PRESETS)
    device = generate_device()
    return DevicePreset(
        label=f"{device['manufacturer']} {device['brand']} {device['model']}",
        code=str(device["profile_code"]),
        manufacturer=str(device["manufacturer"]),
        brand=str(device["brand"]),
        model=str(device["model"]),
        width=int(device["width"]),
        height=int(device["height"]),
        dpi=int(device["dpi"]),
        custom=True,
    )


def random_profile_code() -> str:
    return random.choice(PROFILE_CODE_CHOICES)


def random_manufacturer() -> str:
    return random.choice(MANUFACTURERS)


def random_brand(manufacturer: str | None = None) -> str:
    return _random_brand(manufacturer or random_manufacturer())


def random_model(manufacturer: str | None = None, brand: str | None = None) -> str:
    manufacturer = manufacturer or random_manufacturer()
    brand = brand or _random_brand(manufacturer)
    return _random_model(manufacturer, brand)
