"""Vendor name normalization map.

Maps short / common vendor aliases to their full legal names. Used by
``dbf validate --fix`` to normalize ``manufacturer:`` fields. The C2 seed
dataset references the same canonical names; keep this in sync if vendors
are added there.
"""
from __future__ import annotations

from typing import Optional

VENDOR_MAP: dict[str, str] = {
    "ST": "STMicroelectronics",
    "STM": "STMicroelectronics",
    "Adafruit": "Adafruit Industries",
    "Espressif": "Espressif Systems",
    "TI": "Texas Instruments",
    "NXP": "NXP Semiconductors",
    "Nordic": "Nordic Semiconductor",
    "Microchip": "Microchip Technology",
    "Raspberry Pi": "Raspberry Pi Ltd",
    "Seeed": "Seeed Studio",
    "SparkFun": "SparkFun Electronics",
}

# Lowercase index for case-insensitive lookup.
_LOWER_INDEX: dict[str, str] = {k.lower(): v for k, v in VENDOR_MAP.items()}


def normalize_vendor(name: str) -> Optional[str]:
    """Return the canonical vendor name for ``name``, or None if no mapping."""
    if not isinstance(name, str):
        return None
    canonical = _LOWER_INDEX.get(name.strip().lower())
    if canonical is None:
        return None
    if canonical == name:
        return None  # Already canonical — caller treats None as "no change".
    return canonical
