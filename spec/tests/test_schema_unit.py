"""Unit tests: schema accepts/rejects single fixtures and inline mutations."""
import copy
import pytest
from jsonschema import ValidationError
from conftest import load_fixture


def _validate(validator, doc):
    validator.validate(doc)


def _expect_error(validator, doc, needle):
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(doc)
    msg = str(exc_info.value)
    path = list(exc_info.value.absolute_path)
    assert needle in msg or needle in " ".join(str(p) for p in path), (
        f"expected {needle!r} in error message or path; got msg={msg!r} path={path!r}"
    )


# ── U1–U13 ───────────────────────────────────────────────────────────────────

def test_minimal_valid_passes(validator, minimal_doc):
    _validate(validator, minimal_doc)


def test_extra_top_level_field_passes(validator):
    doc = load_fixture("valid-extra-field.ubds.yaml")
    _validate(validator, doc)


def test_missing_name_rejected(validator):
    doc = load_fixture("invalid-missing-required.ubds.yaml")
    _expect_error(validator, doc, "name")


def test_missing_slug_rejected(validator, minimal_doc):
    del minimal_doc["slug"]
    _expect_error(validator, minimal_doc, "slug")


def test_missing_manufacturer_rejected(validator, minimal_doc):
    del minimal_doc["manufacturer"]
    _expect_error(validator, minimal_doc, "manufacturer")


def test_missing_board_type_rejected(validator, minimal_doc):
    del minimal_doc["board_type"]
    _expect_error(validator, minimal_doc, "board_type")


def test_missing_meta_sources_rejected(validator):
    doc = load_fixture("invalid-missing-sources.ubds.yaml")
    _expect_error(validator, doc, "sources")


def test_empty_meta_sources_rejected(validator):
    doc = load_fixture("invalid-empty-sources.ubds.yaml")
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(doc)
    msg = str(exc_info.value)
    assert "minItems" in msg or "sources" in msg


def test_bad_board_type_enum_rejected(validator):
    doc = load_fixture("invalid-bad-enum.ubds.yaml")
    _expect_error(validator, doc, "board_type")


def test_wrong_type_clock_mhz_rejected(validator):
    doc = load_fixture("invalid-wrong-type.ubds.yaml")
    _expect_error(validator, doc, "clock_mhz")


def test_bad_slug_rejected(validator):
    doc = load_fixture("invalid-bad-slug.ubds.yaml")
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(doc)
    msg = str(exc_info.value)
    assert "slug" in msg or "pattern" in msg


def test_ubds_version_v0_9_rejected(validator, minimal_doc):
    minimal_doc["ubds_version"] = "0.9"
    with pytest.raises(ValidationError):
        validator.validate(minimal_doc)


def test_ubds_version_v1_5_accepted(validator, minimal_doc):
    minimal_doc["ubds_version"] = "1.5"
    validator.validate(minimal_doc)


# ── U14–U20 parametrized enum coverage ──────────────────────────────────────

@pytest.mark.parametrize("value", [
    "MCU", "SBC", "SoM", "Carrier", "Expansion",
    "FPGA", "AI", "SDR", "Industrial", "DSP", "Other",
])
def test_each_board_type_value_accepted(validator, minimal_doc, value):
    minimal_doc["board_type"] = [value]
    validator.validate(minimal_doc)


@pytest.mark.parametrize("value", ["active", "discontinued", "upcoming", "prototype"])
def test_each_status_value_accepted(validator, minimal_doc, value):
    minimal_doc["status"] = value
    validator.validate(minimal_doc)


@pytest.mark.parametrize("value", ["beginner", "intermediate", "advanced"])
def test_each_difficulty_level_value_accepted(validator, minimal_doc, value):
    minimal_doc["difficulty_level"] = value
    validator.validate(minimal_doc)


@pytest.mark.parametrize("value", ["small", "medium", "large", "niche"])
def test_each_ecosystem_size_value_accepted(validator, minimal_doc, value):
    minimal_doc["ecosystem_size"] = value
    validator.validate(minimal_doc)


@pytest.mark.parametrize("value", ["stub", "partial", "complete"])
def test_each_data_completeness_value_accepted(validator, minimal_doc, value):
    minimal_doc["meta"]["data_completeness"] = value
    validator.validate(minimal_doc)


@pytest.mark.parametrize("value", ["low", "medium", "high"])
def test_each_confidence_value_accepted(validator, minimal_doc, value):
    minimal_doc["meta"]["confidence"] = {"processing": value}
    validator.validate(minimal_doc)


@pytest.mark.parametrize("value", [True, False])
def test_top_view_boolean_accepted(validator, minimal_doc, value):
    minimal_doc["metadata"] = {"top_view": value}
    validator.validate(minimal_doc)


# ── U21–U22 nested ──────────────────────────────────────────────────────────

def test_processing_cpu_cores_architecture_validates(validator, minimal_doc):
    minimal_doc["processing"] = [{
        "cpu_cores": [
            {"architecture": "ARM Cortex-M4", "count": 1, "clock_mhz": 240}
        ]
    }]
    validator.validate(minimal_doc)


def test_meta_confidence_processing_high_validates(validator, minimal_doc):
    minimal_doc["meta"]["confidence"] = {"processing": "high"}
    validator.validate(minimal_doc)
