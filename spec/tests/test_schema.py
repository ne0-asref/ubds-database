"""Tests for UBDS v1 JSON Schema validation."""

import json
import copy
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = Path(__file__).parent.parent / "ubds-v1.schema.json"


@pytest.fixture(scope="module")
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


@pytest.fixture
def valid_board():
    """Minimal valid board with all required fields."""
    return {
        "ubds_version": "1.0",
        "name": "Test Board",
        "slug": "test-board",
        "manufacturer": "TestCorp",
        "board_type": ["MCU"],
    }


@pytest.fixture
def full_board():
    """Fully populated board matching the Jetson Orin Nano reference."""
    return {
        "ubds_version": "1.0",
        "name": "NVIDIA Jetson Orin Nano Developer Kit",
        "slug": "jetson-orin-nano-dev-kit",
        "manufacturer": "NVIDIA",
        "series": "Jetson",
        "parent_board": None,
        "hardware_version": "Rev A02",
        "status": "active",
        "release_date": "2023-03-21",
        "end_of_life_date": None,
        "board_type": ["SBC"],
        "difficulty_level": "intermediate",
        "ecosystem_size": "large",
        "use_cases": ["AI/ML", "Robotics", "Edge Computing"],
        "tags": ["CUDA", "JetPack"],
        "processing": [
            {
                "name": "Jetson Orin Nano (8GB)",
                "part_number": "NVIDIA Orin Nano",
                "role": "primary",
                "integrated": True,
                "type": "hybrid",
                "hybrid_components": ["gpu", "npu"],
                "cpu_cores": [
                    {
                        "architecture": "ARM Cortex-A78AE",
                        "bit_width": 64,
                        "count": 6,
                        "clock_mhz": 1500,
                        "features": ["FPU", "NEON", "TrustZone", "Virtualization"],
                    }
                ],
                "gpu": {
                    "architecture": "Ampere",
                    "cuda_cores": 1024,
                    "tensor_cores": 32,
                    "clock_mhz": 625,
                },
                "npu": {"tops": 40, "precision": ["INT8", "FP16"]},
                "memory": {"ram_kb": 8388608},
                "security": {
                    "secure_boot": True,
                    "trustzone": True,
                    "hardware_crypto": True,
                    "crypto_algorithms": ["AES-256", "SHA-256", "RSA", "ECC"],
                    "tamper_detection": False,
                    "secure_storage": True,
                },
            }
        ],
        "interfaces": [
            {
                "connector": "USB-C",
                "label": "J6",
                "classification": "hybrid",
                "count": 1,
                "protocols": [{"name": "USB 3.2 Gen 2", "speed": "10 Gbps"}],
                "power": {
                    "voltage_v": 5,
                    "current_a": 3,
                    "direction": "input",
                    "supports_pd": True,
                },
            }
        ],
        "wireless": [],
        "inputs": [
            {"type": "button", "label": "Power", "count": 1, "function": "power_on_off"}
        ],
        "outputs": [
            {
                "type": "led",
                "label": "Power LED",
                "color": "green",
                "count": 1,
                "function": "power_indicator",
                "programmable": False,
            }
        ],
        "power": {
            "input_voltage_min_v": 9,
            "input_voltage_max_v": 19,
            "recommended_voltage_v": 19,
            "recommended_wattage_w": 45,
            "operating_voltage_v": 5,
        },
        "physical": {
            "dimensions_mm": {"length": 100, "width": 79, "height": 30},
            "weight_g": 140,
            "form_factor": ["Jetson"],
            "breadboard_friendly": False,
        },
        "software": {
            "languages": [
                {"name": "Python", "support_level": "board", "version": "3.8+"}
            ],
            "frameworks": [
                {
                    "name": "JetPack SDK",
                    "support_level": "board",
                    "version": "6.0",
                }
            ],
        },
        "pricing": {
            "msrp_usd": 499,
            "vendors": [
                {
                    "name": "NVIDIA Store",
                    "url": "https://store.nvidia.com/",
                    "price_usd": 499,
                    "in_stock": True,
                }
            ],
        },
        "meta": {
            "sources": ["https://developer.nvidia.com/embedded/learn/get-started-jetson-orin-nano-devkit"],
            "last_verified": "2026-04-05",
            "data_completeness": "full",
            "community_reviewed": False,
            "verified": False,
        },
    }


# ── Test 1: Valid board passes schema ──


def test_minimal_valid_board_passes(schema, valid_board):
    """A board with only required fields should validate."""
    jsonschema.validate(valid_board, schema)


def test_full_valid_board_passes(schema, full_board):
    """The full Jetson Orin Nano reference board should validate."""
    jsonschema.validate(full_board, schema)


# ── Test 2: Missing required field rejected ──


@pytest.mark.parametrize("field", ["name", "slug", "manufacturer", "board_type"])
def test_missing_required_field_rejected(schema, valid_board, field):
    """Removing any required field should fail validation."""
    board = copy.deepcopy(valid_board)
    del board[field]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)


def test_missing_ubds_version_rejected(schema, valid_board):
    """ubds_version is required."""
    board = copy.deepcopy(valid_board)
    del board["ubds_version"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)


def test_missing_meta_sources_rejected(schema, full_board):
    """meta.sources is required when meta is present."""
    board = copy.deepcopy(full_board)
    del board["meta"]["sources"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)


# ── Test 3: Unknown field allowed (extensibility) ──


def test_unknown_top_level_field_allowed(schema, valid_board):
    """Extra fields at top level should not cause validation failure."""
    board = copy.deepcopy(valid_board)
    board["custom_field"] = "some value"
    jsonschema.validate(board, schema)


def test_unknown_nested_field_allowed(schema, full_board):
    """Extra fields in nested objects should not cause validation failure."""
    board = copy.deepcopy(full_board)
    board["power"]["custom_measurement"] = 42
    jsonschema.validate(board, schema)


# ── Test 4: All enum values accepted ──


@pytest.mark.parametrize(
    "board_type",
    [
        "MCU", "SBC", "SoM", "Carrier", "Expansion", "FPGA",
        "AI", "SDR", "Industrial", "DSP", "Other",
    ],
)
def test_all_board_type_enum_values(schema, valid_board, board_type):
    """Every valid board_type value should pass."""
    board = copy.deepcopy(valid_board)
    board["board_type"] = [board_type]
    jsonschema.validate(board, schema)


@pytest.mark.parametrize("status", ["active", "discontinued", "upcoming", "prototype"])
def test_all_status_enum_values(schema, valid_board, status):
    """Every valid status value should pass."""
    board = copy.deepcopy(valid_board)
    board["status"] = status
    jsonschema.validate(board, schema)


@pytest.mark.parametrize("difficulty", ["beginner", "intermediate", "advanced"])
def test_all_difficulty_level_enum_values(schema, valid_board, difficulty):
    """Every valid difficulty_level value should pass."""
    board = copy.deepcopy(valid_board)
    board["difficulty_level"] = difficulty
    jsonschema.validate(board, schema)


@pytest.mark.parametrize("ecosystem", ["small", "medium", "large", "niche"])
def test_all_ecosystem_size_enum_values(schema, valid_board, ecosystem):
    """Every valid ecosystem_size value should pass."""
    board = copy.deepcopy(valid_board)
    board["ecosystem_size"] = ecosystem
    jsonschema.validate(board, schema)


def test_invalid_board_type_rejected(schema, valid_board):
    """An invalid board_type value should fail."""
    board = copy.deepcopy(valid_board)
    board["board_type"] = ["InvalidType"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)


def test_invalid_status_rejected(schema, valid_board):
    """An invalid status value should fail."""
    board = copy.deepcopy(valid_board)
    board["status"] = "invalid_status"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)


# ── Test 5: Nested structure validated ──


def test_processing_cpu_cores_architecture_validated(schema, full_board):
    """processing[].cpu_cores[].architecture must be a string."""
    board = copy.deepcopy(full_board)
    board["processing"][0]["cpu_cores"][0]["architecture"] = 12345
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)


def test_processing_requires_name(schema, valid_board):
    """processing[] items require name field."""
    board = copy.deepcopy(valid_board)
    board["processing"] = [{"type": "mcu"}]  # missing name
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)


def test_interface_classification_enum(schema, full_board):
    """Interface classification must be one of power|data|debug|hybrid."""
    board = copy.deepcopy(full_board)
    board["interfaces"][0]["classification"] = "invalid"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)


def test_processing_type_enum(schema, valid_board):
    """Processing element type must be valid enum."""
    board = copy.deepcopy(valid_board)
    board["processing"] = [
        {"name": "Test", "type": "quantum_computer"}  # invalid type
    ]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)


def test_data_completeness_enum(schema, full_board):
    """meta.data_completeness must be full|partial|stub."""
    board = copy.deepcopy(full_board)
    board["meta"]["data_completeness"] = "incomplete"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)


def test_board_type_must_be_array(schema, valid_board):
    """board_type must be an array, not a string."""
    board = copy.deepcopy(valid_board)
    board["board_type"] = "MCU"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)


def test_board_type_requires_at_least_one(schema, valid_board):
    """board_type array must have at least one item."""
    board = copy.deepcopy(valid_board)
    board["board_type"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)


def test_power_direction_enum(schema, full_board):
    """power.direction on interfaces must be input|output|bidirectional."""
    board = copy.deepcopy(full_board)
    board["interfaces"][0]["power"]["direction"] = "sideways"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)


def test_confidence_level_enum(schema, full_board):
    """meta.confidence values must be high|medium|low."""
    board = copy.deepcopy(full_board)
    board["meta"]["confidence"] = {"processing": "very_high"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)


def test_support_level_enum(schema, full_board):
    """software.languages[].support_level must be valid."""
    board = copy.deepcopy(full_board)
    board["software"]["languages"][0]["support_level"] = "maybe"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(board, schema)
