"""Tests for PlatformIO board import."""

import json
from pathlib import Path

from click.testing import CliRunner

from dbf.cli import cli
from dbf.importers.platformio import convert_platformio_board


def test_convert_known_board(sample_platformio_board):
    """Known PlatformIO board maps to correct UBDS fields."""
    ubds = convert_platformio_board(sample_platformio_board)
    assert ubds["name"] == "Espressif ESP32 Dev Module"
    assert ubds["slug"] == "esp32dev"
    assert ubds["manufacturer"] == "Espressif"
    assert ubds["ubds_version"] == "1.0"
    assert "MCU" in ubds["board_type"]
    # Processing
    assert len(ubds["processing"]) == 1
    pe = ubds["processing"][0]
    assert pe["cpu_cores"][0]["clock_mhz"] == 240
    # Memory
    assert pe["memory"]["ram_kb"] == 320  # 327680 bytes = 320 KB
    assert pe["memory"]["flash_kb"] == 4096  # 4194304 bytes = 4096 KB
    # Wireless from connectivity
    wireless_protocols = [w["protocol"].lower() for w in ubds.get("wireless", [])]
    assert "wifi" in wireless_protocols
    assert "bluetooth" in wireless_protocols
    # Software frameworks
    frameworks = [f["name"].lower() for f in ubds.get("software", {}).get("frameworks", [])]
    assert "arduino" in frameworks
    assert "esp-idf" in frameworks


def test_convert_minimal_board(sample_platformio_board_minimal):
    """PlatformIO board with minimal fields still produces valid UBDS."""
    ubds = convert_platformio_board(sample_platformio_board_minimal)
    assert ubds["name"] == "Unknown Board"
    assert ubds["slug"] == "unknown-board"
    assert ubds["ubds_version"] == "1.0"
    assert ubds["board_type"] == ["MCU"]
    assert ubds["meta"]["data_completeness"] == "partial"


def test_convert_handles_missing_fields(sample_platformio_board_minimal):
    """Partial PlatformIO data produces data_completeness: partial."""
    ubds = convert_platformio_board(sample_platformio_board_minimal)
    assert ubds["meta"]["data_completeness"] == "partial"
    assert "wireless" not in ubds or ubds.get("wireless") == []


def test_import_single_file(tmp_path, sample_platformio_board):
    """CLI imports a single PlatformIO JSON file."""
    json_file = tmp_path / "esp32dev.json"
    json_file.write_text(json.dumps(sample_platformio_board))
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["import", "platformio", str(json_file), "--output-dir", str(output_dir)])
    assert result.exit_code == 0
    output_files = list(output_dir.glob("*.ubds.yaml"))
    assert len(output_files) == 1


def test_import_directory(tmp_path, sample_platformio_board, sample_platformio_board_minimal):
    """CLI imports all .json files from a directory."""
    input_dir = tmp_path / "boards"
    input_dir.mkdir()
    (input_dir / "esp32dev.json").write_text(json.dumps(sample_platformio_board))
    (input_dir / "unknown.json").write_text(json.dumps(sample_platformio_board_minimal))
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["import", "platformio", str(input_dir), "--output-dir", str(output_dir)])
    assert result.exit_code == 0
    output_files = list(output_dir.glob("*.ubds.yaml"))
    assert len(output_files) == 2
