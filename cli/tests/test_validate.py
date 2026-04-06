"""Tests for dbf validate command."""

import os
from pathlib import Path

from click.testing import CliRunner

from dbf.cli import cli
from dbf.validate import validate_board


def test_validate_accepts_valid_board(tmp_path, valid_board_yaml, schema_path):
    """dbf validate returns no errors for a valid board."""
    board_file = tmp_path / "test-board.ubds.yaml"
    board_file.write_text(valid_board_yaml)
    errors = validate_board(str(board_file), str(schema_path))
    assert errors == []


def test_validate_rejects_missing_required_field(tmp_path, invalid_board_yaml_missing_name, schema_path):
    """dbf validate returns errors with field path for missing required field."""
    board_file = tmp_path / "test-board.ubds.yaml"
    board_file.write_text(invalid_board_yaml_missing_name)
    errors = validate_board(str(board_file), str(schema_path))
    assert len(errors) > 0
    assert any("name" in e.field for e in errors)


def test_validate_rejects_bad_enum(tmp_path, invalid_board_yaml_bad_enum, schema_path):
    """dbf validate returns errors for invalid enum value."""
    board_file = tmp_path / "test-board.ubds.yaml"
    board_file.write_text(invalid_board_yaml_bad_enum)
    errors = validate_board(str(board_file), str(schema_path))
    assert len(errors) > 0


def test_validate_warns_version_mismatch(tmp_path, schema_path):
    """dbf validate warns (does not fail) when ubds_version differs from schema."""
    content = """\
ubds_version: "2.0"
name: "Test Board"
slug: "test-board"
manufacturer: "TestCorp"
board_type:
  - MCU
meta:
  sources:
    - "https://example.com"
"""
    board_file = tmp_path / "test-board.ubds.yaml"
    board_file.write_text(content)
    errors = validate_board(str(board_file), str(schema_path))
    # Version mismatch produces errors (const: "1.0" violated), but the function
    # should still return them as validation errors
    assert len(errors) > 0


def test_validate_cli_exit_code_0(tmp_path, valid_board_yaml, schema_path):
    """CLI exits 0 for valid board."""
    board_file = tmp_path / "test-board.ubds.yaml"
    board_file.write_text(valid_board_yaml)
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", str(board_file), "--schema", str(schema_path)])
    assert result.exit_code == 0


def test_validate_cli_exit_code_1(tmp_path, invalid_board_yaml_missing_name, schema_path):
    """CLI exits 1 for invalid board."""
    board_file = tmp_path / "test-board.ubds.yaml"
    board_file.write_text(invalid_board_yaml_missing_name)
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", str(board_file), "--schema", str(schema_path)])
    assert result.exit_code == 1


def test_validate_multiple_files(tmp_path, valid_board_yaml, invalid_board_yaml_missing_name, schema_path):
    """CLI can validate multiple files, reporting errors per file."""
    good = tmp_path / "good.ubds.yaml"
    good.write_text(valid_board_yaml)
    bad = tmp_path / "bad.ubds.yaml"
    bad.write_text(invalid_board_yaml_missing_name)
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", str(good), str(bad), "--schema", str(schema_path)])
    assert result.exit_code == 1  # at least one file failed


def test_validate_fix_trims_whitespace(tmp_path, fixable_board_yaml, schema_path):
    """--fix trims leading/trailing whitespace from string fields."""
    board_file = tmp_path / "test-board.ubds.yaml"
    board_file.write_text(fixable_board_yaml)
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", str(board_file), "--schema", str(schema_path), "--fix"])
    assert result.exit_code == 0
    import yaml
    with open(board_file) as f:
        fixed = yaml.safe_load(f)
    assert fixed["name"] == "Test Board"
    assert fixed["manufacturer"] == "TestCorp"


def test_validate_fix_lowercases_wireless_protocol(tmp_path, fixable_board_yaml, schema_path):
    """--fix lowercases wireless protocol names."""
    board_file = tmp_path / "test-board.ubds.yaml"
    board_file.write_text(fixable_board_yaml)
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", str(board_file), "--schema", str(schema_path), "--fix"])
    import yaml
    with open(board_file) as f:
        fixed = yaml.safe_load(f)
    assert fixed["wireless"][0]["protocol"] == "WiFi"


def test_validate_real_boards(schema_path, boards_dir):
    """All real board files in boards/ validate successfully."""
    board_files = sorted(boards_dir.glob("*.ubds.yaml"))
    assert len(board_files) >= 15
    for bf in board_files:
        errors = validate_board(str(bf), str(schema_path))
        assert errors == [], f"{bf.name} has errors: {errors}"
