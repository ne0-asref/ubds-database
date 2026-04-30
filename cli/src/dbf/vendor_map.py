"""Vendor name normalization map.

Maps short / common vendor aliases to their full legal names. Used by
``dbf validate --fix`` to normalize ``manufacturer:`` fields. The C2 seed
dataset references the same canonical names; keep this in sync if vendors
are added there.

Also exposes :func:`slug_for_manufacturer` — the canonical-name → directory
slug mapping used by C22 U2's filesystem nesting migration and (later) by
``dbf migrate`` to populate ``manufacturer_slug:``. Unmapped vendors fall
through to ``"unknown"`` per ubds-spec-revision-handoff §5.
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


# Canonical manufacturer name → directory-slug. Covers every manufacturer
# present in boards/ today plus the 14 well-known vendors named in the
# C22 eng-plan §5 handoff. Slugs follow the lowercase-kebab pattern from
# ubds-manufacturer.schema.json (^[a-z0-9]+(-[a-z0-9]+)*$).
_CANONICAL_TO_SLUG: dict[str, str] = {
    "Adafruit Industries": "adafruit-industries",
    "Arduino": "arduino",
    "BeagleBoard.org Foundation": "beagleboard",
    "Espressif Systems": "espressif",
    "Lattice Semiconductor": "lattice",
    "Microchip Technology": "microchip",
    "NVIDIA": "nvidia",
    "NXP Semiconductors": "nxp",
    "Nordic Semiconductor": "nordic",
    "Raspberry Pi Foundation": "raspberry-pi",
    "Raspberry Pi Ltd": "raspberry-pi",
    "Renesas": "renesas",
    "Seeed Studio": "seeed",
    "Sipeed": "sipeed",
    "SparkFun Electronics": "sparkfun",
    "STMicroelectronics": "st",
    "Texas Instruments": "ti",
    "WCH": "wch",
}

UNKNOWN_MANUFACTURER_SLUG = "unknown"


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


def slug_for_manufacturer(name: str) -> str:
    """Return the directory slug for a manufacturer name.

    Accepts either a canonical name (``"Espressif Systems"``) or a known
    short alias (``"Espressif"``). Returns :data:`UNKNOWN_MANUFACTURER_SLUG`
    when the input is unknown — callers nest the board under
    ``boards/unknown/`` per handoff §5.
    """
    if not isinstance(name, str):
        return UNKNOWN_MANUFACTURER_SLUG
    stripped = name.strip()
    if not stripped:
        return UNKNOWN_MANUFACTURER_SLUG
    # Direct canonical hit.
    if stripped in _CANONICAL_TO_SLUG:
        return _CANONICAL_TO_SLUG[stripped]
    # Try resolving an alias to its canonical, then map.
    alias_target = _LOWER_INDEX.get(stripped.lower())
    if alias_target is not None and alias_target in _CANONICAL_TO_SLUG:
        return _CANONICAL_TO_SLUG[alias_target]
    return UNKNOWN_MANUFACTURER_SLUG
