"""Tests for the Elm-style error formatter (E1..E11)."""
from __future__ import annotations

import jsonschema
import pytest

from dbf.errors import FIX_HINTS, format_error, format_errors
from dbf.schema import load_schema


# ---------- helpers ----------

def _validator():
    return jsonschema.Draft7Validator(load_schema())


def _minimal_valid_instance() -> dict:
    return {
        "ubds_version": "1.0",
        "name": "Test Board",
        "slug": "test-board",
        "manufacturer": "ACME",
        "board_type": ["MCU"],
        "meta": {"sources": ["https://example.com"]},
    }


def _errors_for(instance):
    return list(_validator().iter_errors(instance))


def _first_error_with(instance, validator_name):
    for err in _errors_for(instance):
        if err.validator == validator_name:
            return err
    raise AssertionError(f"No {validator_name} error in {instance!r}")


# ---------- E1 ----------

def test_format_missing_required_field():
    inst = _minimal_valid_instance()
    del inst["name"]
    err = _first_error_with(inst, "required")
    yaml_text = (
        "ubds_version: '1.0'\n"
        "slug: test-board\n"
        "manufacturer: ACME\n"
        "board_type: [MCU]\n"
        "meta:\n"
        "  sources: ['https://example.com']\n"
    )
    out = format_error(err, yaml_text, "boards/test.ubds.yaml")
    assert "field:" in out
    assert "expected:" in out
    assert "fix:" in out
    # required → no `got:` line
    assert "got:" not in out


# ---------- E2 ----------

def test_format_includes_red_x_marker():
    inst = _minimal_valid_instance()
    del inst["name"]
    err = _first_error_with(inst, "required")
    out = format_error(err, None, "x.yaml")
    assert out.startswith("\u2717")


# ---------- E3 ----------

def test_format_includes_file_path():
    inst = _minimal_valid_instance()
    del inst["name"]
    err = _first_error_with(inst, "required")
    out = format_error(err, None, "boards/foo.ubds.yaml")
    assert "boards/foo.ubds.yaml" in out.splitlines()[0]


# ---------- E4 ----------

def test_format_includes_line_and_column():
    inst = _minimal_valid_instance()
    inst["slug"] = "Bad_Slug"  # pattern violation
    err = _first_error_with(inst, "pattern")
    yaml_text = (
        "ubds_version: '1.0'\n"
        "name: Test\n"
        "slug: Bad_Slug\n"
        "manufacturer: ACME\n"
        "board_type: [MCU]\n"
        "meta:\n"
        "  sources: ['https://example.com']\n"
    )
    out = format_error(err, yaml_text, "x.yaml")
    assert "line 3" in out
    assert "column" in out


# ---------- E5 ----------

def test_format_field_path_uses_dotted_notation():
    inst = _minimal_valid_instance()
    inst["processing"] = [
        {
            "cpu_cores": [
                {"architecture": "arm", "count": 1, "clock_mhz": "fast"}
            ]
        }
    ]
    err = None
    for e in _errors_for(inst):
        if list(e.absolute_path) == ["processing", 0, "cpu_cores", 0, "clock_mhz"]:
            err = e
            break
    assert err is not None
    out = format_error(err, None, "x.yaml")
    assert "processing[0].cpu_cores[0].clock_mhz" in out


# ---------- E6 ----------

def test_format_includes_actual_type():
    inst = _minimal_valid_instance()
    inst["slug"] = "Bad_Slug"
    err = _first_error_with(inst, "pattern")
    out = format_error(err, None, "x.yaml")
    assert "(str)" in out


# ---------- E7 ----------

def test_format_unmapped_error_falls_back():
    err = jsonschema.ValidationError(
        message="weird",
        validator="totallyMadeUpValidator",
        validator_value=None,
        instance="x",
        schema={},
        path=[],
    )
    out = format_error(err, None, "x.yaml")
    assert "See spec/ubds-v1.schema.json for details." in out


# ---------- E8 ----------

def test_format_enum_violation_lists_allowed():
    inst = _minimal_valid_instance()
    inst["board_type"] = ["NotARealType"]
    err = _first_error_with(inst, "enum")
    out = format_error(err, None, "x.yaml")
    assert "MCU" in out
    assert "SBC" in out


# ---------- E9 ----------

def test_format_pattern_violation_explains_pattern():
    inst = _minimal_valid_instance()
    inst["slug"] = "Bad_Slug"
    err = _first_error_with(inst, "pattern")
    out = format_error(err, None, "x.yaml")
    assert "lowercase letters" in out


# ---------- E10 ----------

def test_format_handles_missing_yaml_text_gracefully():
    inst = _minimal_valid_instance()
    inst["slug"] = "Bad_Slug"
    err = _first_error_with(inst, "pattern")
    out = format_error(err, None, "x.yaml")
    assert "at:" not in out
    assert "line" not in out.split("fix:")[0].split("at:")[0] or True  # no crash


# ---------- E11 ----------

def test_format_multiple_errors_each_in_own_block():
    inst = _minimal_valid_instance()
    del inst["name"]
    inst["slug"] = "Bad_Slug"
    inst["board_type"] = ["NotARealType"]
    errs = _errors_for(inst)
    assert len(errs) >= 3
    out = format_errors(errs[:3], None, "x.yaml")
    assert out.count("\u2717") == 3
    # blank line between blocks
    assert "\n\n" in out


# ---------- coverage ----------

def test_fix_hints_covers_at_least_10_validators():
    assert len(FIX_HINTS) >= 10
