"""Board YAML validation against UBDS JSON Schema."""

import json
from pathlib import Path

import jsonschema
import yaml

from dbf.data import StrDateLoader
from dbf.errors import ValidationError, format_validation_error


def validate_board(board_path: str, schema_path: str) -> list[ValidationError]:
    """Validate a board YAML file against the JSON Schema.

    Returns a list of ValidationError objects. Empty list means valid.
    """
    with open(schema_path) as f:
        schema = json.load(f)

    with open(board_path) as f:
        board = yaml.load(f, Loader=StrDateLoader)

    if board is None:
        return [ValidationError(
            field="(file)",
            message="File is empty or not valid YAML",
            fix_suggestion="Add board data to the YAML file.",
        )]

    errors = []
    validator = jsonschema.Draft202012Validator(schema)

    for error in sorted(validator.iter_errors(board), key=lambda e: list(e.path)):
        field_path = ".".join(str(p) for p in error.absolute_path)
        errors.append(format_validation_error(
            field_path=field_path,
            message=error.message,
            validator=error.validator,
            schema_path=list(str(p) for p in error.absolute_schema_path),
            instance=error.instance,
        ))

    return errors


def apply_fixes(board_path: str) -> list[str]:
    """Apply auto-fixes to a board YAML file. Returns list of fixes applied.

    Fixes:
    - Trim leading/trailing whitespace from string fields
    - Normalize wireless protocol casing (WiFi, Bluetooth, LoRa, etc.)
    - Normalize framework/language casing
    """
    with open(board_path) as f:
        board = yaml.load(f, Loader=StrDateLoader)

    if board is None:
        return []

    fixes = []

    # Fix 1: Trim whitespace from top-level string fields
    for key in ("name", "manufacturer", "series", "hardware_version"):
        if key in board and isinstance(board[key], str) and board[key] != board[key].strip():
            board[key] = board[key].strip()
            fixes.append(f"Trimmed whitespace from '{key}'")

    # Fix 2: Normalize wireless protocol names
    protocol_map = {
        "wifi": "WiFi",
        "bluetooth": "Bluetooth",
        "ble": "BLE",
        "lora": "LoRa",
        "zigbee": "Zigbee",
        "thread": "Thread",
        "nfc": "NFC",
        "uwb": "UWB",
        "cellular": "Cellular",
    }
    for wireless in board.get("wireless", []):
        proto = wireless.get("protocol", "")
        normalized = protocol_map.get(proto.lower())
        if normalized and proto != normalized:
            wireless["protocol"] = normalized
            fixes.append(f"Normalized wireless protocol '{proto}' → '{normalized}'")

    # Fix 3: Normalize framework/language names (title case common ones)
    name_map = {
        "arduino": "Arduino",
        "micropython": "MicroPython",
        "circuitpython": "CircuitPython",
        "platformio": "PlatformIO",
        "esp-idf": "ESP-IDF",
        "zephyr": "Zephyr",
        "freertos": "FreeRTOS",
        "mbed": "Mbed OS",
        "python": "Python",
        "rust": "Rust",
        "c": "C",
        "c++": "C++",
        "cpp": "C++",
    }
    for section_key in ("frameworks", "languages"):
        for entry in board.get("software", {}).get(section_key, []):
            name = entry.get("name", "")
            normalized = name_map.get(name.lower())
            if normalized and name != normalized:
                entry["name"] = normalized
                fixes.append(f"Normalized {section_key} name '{name}' → '{normalized}'")

    if fixes:
        with open(board_path, "w") as f:
            yaml.dump(board, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return fixes
