"""Edge cases: empty arrays, zero values, dates, slug regex boundaries."""
import pytest
from jsonschema import ValidationError


def test_empty_use_cases_array_passes(validator, minimal_doc):
    minimal_doc["use_cases"] = []
    validator.validate(minimal_doc)


def test_zero_clock_mhz_passes(validator, minimal_doc):
    minimal_doc["processing"] = [{
        "cpu_cores": [{"architecture": "ARM", "count": 1, "clock_mhz": 0}]
    }]
    validator.validate(minimal_doc)


def test_invalid_date_format_rejected(validator, minimal_doc):
    minimal_doc["release_date"] = "March 21, 2023"
    with pytest.raises(ValidationError):
        validator.validate(minimal_doc)


def test_valid_iso_date_passes(validator, minimal_doc):
    minimal_doc["release_date"] = "2023-03-21"
    validator.validate(minimal_doc)


def test_slug_min_length(validator, minimal_doc):
    minimal_doc["slug"] = "a1"
    validator.validate(minimal_doc)
    minimal_doc["slug"] = "a"
    with pytest.raises(ValidationError):
        validator.validate(minimal_doc)


def test_slug_uppercase_rejected(validator, minimal_doc):
    minimal_doc["slug"] = "ESP32"
    with pytest.raises(ValidationError):
        validator.validate(minimal_doc)


def test_slug_underscore_rejected(validator, minimal_doc):
    minimal_doc["slug"] = "esp_32"
    with pytest.raises(ValidationError):
        validator.validate(minimal_doc)


def test_slug_trailing_hyphen_rejected(validator, minimal_doc):
    minimal_doc["slug"] = "esp32-"
    with pytest.raises(ValidationError):
        validator.validate(minimal_doc)


def test_parent_board_null_passes(validator, minimal_doc):
    minimal_doc["parent_board"] = None
    validator.validate(minimal_doc)


def test_parent_board_string_passes(validator, minimal_doc):
    minimal_doc["parent_board"] = "esp32-devkit-v1"
    validator.validate(minimal_doc)


def test_meta_sources_must_be_uri(validator, minimal_doc):
    minimal_doc["meta"]["sources"] = ["not a url"]
    with pytest.raises(ValidationError):
        validator.validate(minimal_doc)


def test_board_type_with_two_values_passes(validator, minimal_doc):
    minimal_doc["board_type"] = ["FPGA", "MCU"]
    validator.validate(minimal_doc)


def test_board_type_empty_array_rejected(validator, minimal_doc):
    minimal_doc["board_type"] = []
    with pytest.raises(ValidationError):
        validator.validate(minimal_doc)
