"""Source-of-truth mapping from PlatformIO board JSON to UBDS board dicts.

Other components (notably C2 spec) reference this module by name. Keep the
``MAP`` table and ``map_pio_to_ubds`` function in sync with the C2 spec
§"Step 2: Per board, harvest from PIO JSON".
"""
from __future__ import annotations

from typing import Any

from ..vendor_map import normalize_vendor

# Static reference table — used for documentation/inspection. The actual
# transform lives in ``map_pio_to_ubds`` below because most fields require
# small bits of normalization (lowercasing, unit conversion, filtering).
MAP: dict[str, str] = {
    "name": "name",
    "vendor": "manufacturer",
    "build.mcu": "processing[0].cpu_cores[0].architecture",
    "build.f_cpu": "processing[0].cpu_cores[0].clock_mhz",
    "upload.maximum_ram_size": "processing[0].memory.ram_kb",
    "upload.maximum_size": "processing[0].memory.flash_kb",
    "frameworks": "software.frameworks[].name",
    "connectivity": "wireless[].protocol | interfaces.<name>",
    "url": "meta.sources[0]",
}

# Connectivity tokens that map to ``wireless[].protocol`` entries.
WIRELESS_PROTOCOLS: set[str] = {
    "wifi",
    "bluetooth",
    "ble",
    "lora",
    "cellular",
    "thread",
    "zigbee",
}

# Connectivity tokens that map to boolean entries under ``interfaces``.
INTERFACE_CONNECTIVITY: set[str] = {
    "can",
    "i2c",
    "spi",
    "uart",
    "usb",
    "ethernet",
}


def _parse_f_cpu(raw: Any) -> int | None:
    """Parse PIO ``build.f_cpu`` (e.g. ``"240000000L"``) to MHz int."""
    if raw is None:
        return None
    s = str(raw).strip().rstrip("Ll")
    try:
        hz = int(s)
    except ValueError:
        return None
    return hz // 1_000_000


def map_pio_to_ubds(pio: dict, *, source_url: str, slug: str) -> dict:
    """Transform a PlatformIO board JSON dict into a UBDS board dict."""
    vendor_raw = pio.get("vendor", "") or ""
    manufacturer = normalize_vendor(vendor_raw) or vendor_raw

    build = pio.get("build", {}) or {}
    upload = pio.get("upload", {}) or {}

    architecture = build.get("mcu") or ""
    clock_mhz = _parse_f_cpu(build.get("f_cpu"))

    # PlatformIO does not expose core count; omit rather than fabricate.
    cpu_core: dict[str, Any] = {
        "architecture": architecture,
    }
    if clock_mhz is not None:
        cpu_core["clock_mhz"] = clock_mhz

    memory: dict[str, Any] = {}
    ram = upload.get("maximum_ram_size")
    flash = upload.get("maximum_size")
    if isinstance(ram, int):
        memory["ram_kb"] = ram // 1024
    if isinstance(flash, int):
        memory["flash_kb"] = flash // 1024

    processing_entry: dict[str, Any] = {"cpu_cores": [cpu_core]}
    if memory:
        processing_entry["memory"] = memory

    frameworks = [
        {"name": str(name).lower()} for name in (pio.get("frameworks") or [])
    ]

    connectivity = [str(c).lower() for c in (pio.get("connectivity") or [])]
    wireless = [
        {"protocol": p} for p in connectivity if p in WIRELESS_PROTOCOLS
    ]
    interfaces: dict[str, bool] = {
        c: True for c in connectivity if c in INTERFACE_CONNECTIVITY
    }

    board: dict[str, Any] = {
        "ubds_version": "1.0",
        "slug": slug,
        "name": pio.get("name", ""),
        "manufacturer": manufacturer,
        "board_type": ["MCU"],
        "processing": [processing_entry],
    }
    if frameworks:
        board["software"] = {"frameworks": frameworks}
    if wireless:
        board["wireless"] = wireless
    if interfaces:
        board["interfaces"] = interfaces

    board["meta"] = {
        "data_completeness": "stub",
        "confidence": {"processing": "high", "software": "high"},
        "sources": [source_url],
    }
    return board
