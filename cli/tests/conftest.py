"""Shared test fixtures for dbf CLI tests."""

import json
from pathlib import Path

import pytest

# Paths relative to this test file
PROJECT_ROOT = Path(__file__).parent.parent.parent  # worktrees/lane-a/
SCHEMA_PATH = PROJECT_ROOT / "spec" / "ubds-v1.schema.json"
BOARDS_DIR = PROJECT_ROOT / "boards"


@pytest.fixture(scope="session")
def schema_path():
    return SCHEMA_PATH


@pytest.fixture(scope="session")
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def boards_dir():
    return BOARDS_DIR


@pytest.fixture
def valid_board_yaml():
    """Minimal valid UBDS YAML content."""
    return """\
ubds_version: "1.0"
name: "Test Board"
slug: "test-board"
manufacturer: "TestCorp"
board_type:
  - MCU
meta:
  sources:
    - "https://example.com/test-board"
  data_completeness: partial
  community_reviewed: false
  verified: false
"""


@pytest.fixture
def invalid_board_yaml_missing_name():
    """UBDS YAML missing required 'name' field."""
    return """\
ubds_version: "1.0"
slug: "test-board"
manufacturer: "TestCorp"
board_type:
  - MCU
meta:
  sources:
    - "https://example.com/test-board"
"""


@pytest.fixture
def invalid_board_yaml_bad_enum():
    """UBDS YAML with invalid board_type enum."""
    return """\
ubds_version: "1.0"
name: "Test Board"
slug: "test-board"
manufacturer: "TestCorp"
board_type:
  - InvalidType
meta:
  sources:
    - "https://example.com/test-board"
"""


@pytest.fixture
def fixable_board_yaml():
    """UBDS YAML with issues that --fix can correct."""
    return """\
ubds_version: "1.0"
name: "  Test Board  "
slug: "test-board"
manufacturer: "  TestCorp  "
board_type:
  - MCU
wireless:
  - protocol: WIFI
    version: "6"
software:
  frameworks:
    - name: ARDUINO
      support_level: board
  languages:
    - name: PYTHON
      support_level: board
meta:
  sources:
    - "https://example.com/test-board"
"""


@pytest.fixture
def sample_platformio_board():
    """PlatformIO board JSON for an ESP32."""
    return {
        "id": "esp32dev",
        "name": "Espressif ESP32 Dev Module",
        "platform": "espressif32",
        "url": "https://docs.espressif.com/projects/esp-idf/en/latest/esp32/hw-reference/esp32/get-started-devkitc.html",
        "vendor": "Espressif",
        "frameworks": ["arduino", "espidf"],
        "mcu": "ESP32",
        "fcpu": 240000000,
        "ram": 327680,
        "rom": 4194304,
        "connectivity": ["wifi", "bluetooth", "ethernet", "can"],
        "debug": {
            "tools": {
                "esp-prog": {"onboard": False},
                "minimodule": {"onboard": False},
            }
        },
    }


@pytest.fixture
def sample_platformio_board_minimal():
    """PlatformIO board JSON with minimal fields."""
    return {
        "id": "unknown_board",
        "name": "Unknown Board",
        "vendor": "Unknown",
        "mcu": "UNKNOWN",
        "fcpu": 16000000,
        "ram": 2048,
        "rom": 32768,
    }
