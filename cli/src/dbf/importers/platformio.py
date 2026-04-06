"""Convert PlatformIO board JSON to UBDS YAML."""

import json
import re
from pathlib import Path

import yaml


# Map PlatformIO connectivity strings to UBDS wireless protocols
_CONNECTIVITY_MAP = {
    "wifi": {"protocol": "WiFi"},
    "bluetooth": {"protocol": "Bluetooth"},
    "ethernet": None,  # Not wireless
    "can": None,
    "zigbee": {"protocol": "Zigbee"},
    "thread": {"protocol": "Thread"},
    "lora": {"protocol": "LoRa"},
}

# Map PlatformIO framework IDs to display names
_FRAMEWORK_MAP = {
    "arduino": "Arduino",
    "espidf": "ESP-IDF",
    "zephyr": "Zephyr",
    "mbed": "Mbed OS",
    "freertos": "FreeRTOS",
    "stm32cube": "STM32Cube",
    "cmsis": "CMSIS",
    "libopencm3": "libopencm3",
    "spl": "SPL",
    "simba": "Simba",
    "wiringpi": "WiringPi",
}


def convert_platformio_board(pio_board: dict) -> dict:
    """Convert a PlatformIO board JSON object to UBDS format."""

    name = pio_board.get("name", "Unknown Board")
    slug = _slugify(pio_board.get("id", name))

    # Processing element
    mcu = pio_board.get("mcu", "Unknown")
    fcpu = pio_board.get("fcpu", 0)
    ram_bytes = pio_board.get("ram", 0)
    rom_bytes = pio_board.get("rom", 0)

    processing = [{
        "name": mcu,
        "type": "mcu",
        "role": "primary",
        "cpu_cores": [{
            "architecture": mcu,
            "clock_mhz": fcpu // 1_000_000 if fcpu else 0,
        }],
        "memory": {
            "ram_kb": ram_bytes // 1024 if ram_bytes else 0,
            "flash_kb": rom_bytes // 1024 if rom_bytes else 0,
        },
    }]

    # Wireless from connectivity
    wireless = []
    for conn in pio_board.get("connectivity", []):
        mapped = _CONNECTIVITY_MAP.get(conn.lower())
        if mapped:
            wireless.append(mapped)

    # Software frameworks
    frameworks = []
    for fw_id in pio_board.get("frameworks", []):
        fw_name = _FRAMEWORK_MAP.get(fw_id, fw_id)
        frameworks.append({
            "name": fw_name,
            "support_level": "board",
        })

    software = {}
    if frameworks:
        software["frameworks"] = frameworks

    # Determine data completeness
    has_url = bool(pio_board.get("url"))
    has_connectivity = bool(pio_board.get("connectivity"))
    has_frameworks = bool(pio_board.get("frameworks"))
    completeness = "partial"  # PlatformIO data is always partial for UBDS

    # Build UBDS board
    ubds: dict = {
        "ubds_version": "1.0",
        "name": name,
        "slug": slug,
        "manufacturer": pio_board.get("vendor", "Unknown"),
        "board_type": ["MCU"],
    }

    ubds["processing"] = processing

    if wireless:
        ubds["wireless"] = wireless
    else:
        ubds["wireless"] = []

    if software:
        ubds["software"] = software

    # Metadata
    meta: dict = {
        "sources": [],
        "data_completeness": completeness,
        "community_reviewed": False,
        "verified": False,
    }
    if has_url:
        meta["sources"].append(pio_board["url"])
    if not meta["sources"]:
        meta["sources"].append(f"https://registry.platformio.org/boards/{slug}")

    ubds["meta"] = meta

    return ubds


def convert_platformio_file(json_path: Path, output_dir: Path) -> Path:
    """Convert a PlatformIO JSON file to a UBDS YAML file."""
    with open(json_path) as f:
        pio_board = json.load(f)

    ubds = convert_platformio_board(pio_board)
    slug = ubds["slug"]
    output_path = output_dir / f"{slug}.ubds.yaml"

    with open(output_path, "w") as f:
        yaml.dump(ubds, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return output_path


def convert_platformio_directory(input_dir: Path, output_dir: Path) -> list[Path]:
    """Convert all .json files in a directory to UBDS YAML."""
    results = []
    for json_file in sorted(input_dir.glob("*.json")):
        try:
            result = convert_platformio_file(json_file, output_dir)
            results.append(result)
        except Exception:
            continue
    return results


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text
