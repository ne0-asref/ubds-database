"""Tests for Elm-style error formatting."""

from dbf.errors import format_validation_error


def test_format_missing_required_field():
    """Error for missing required field shows field path and fix suggestion."""
    err = format_validation_error(
        field_path="",
        message="'name' is a required property",
        validator="required",
        schema_path=["required"],
        instance={},
    )
    assert "name" in err.field
    assert "required" in err.message.lower()
    assert err.fix_suggestion is not None


def test_format_invalid_enum():
    """Error for invalid enum shows expected values."""
    err = format_validation_error(
        field_path="status",
        message="'invalid' is not one of ['active', 'discontinued', 'upcoming', 'prototype']",
        validator="enum",
        schema_path=["properties", "status", "enum"],
        instance="invalid",
    )
    assert err.field == "status"
    assert "invalid" in err.message
    assert err.expected is not None


def test_format_wrong_type():
    """Error for wrong type shows expected vs got."""
    err = format_validation_error(
        field_path="board_type",
        message="'MCU' is not of type 'array'",
        validator="type",
        schema_path=["properties", "board_type", "type"],
        instance="MCU",
    )
    assert err.field == "board_type"
    assert err.got is not None
    assert err.expected is not None


def test_format_error_has_all_fields():
    """Formatted error has field, message, expected, got, fix_suggestion."""
    err = format_validation_error(
        field_path="meta.sources",
        message="[] should be non-empty",
        validator="minItems",
        schema_path=["properties", "meta", "properties", "sources", "minItems"],
        instance=[],
    )
    assert hasattr(err, "field")
    assert hasattr(err, "message")
    assert hasattr(err, "expected")
    assert hasattr(err, "got")
    assert hasattr(err, "fix_suggestion")
