"""Tests for dbf info command."""

from click.testing import CliRunner

from dbf.cli import cli
from dbf.info import get_board_info


def test_info_displays_board_details(boards_dir):
    """info returns structured data for a known board."""
    info = get_board_info("raspberry-pi-pico", boards_dir)
    assert info is not None
    assert info["name"] == "Raspberry Pi Pico"
    assert info["manufacturer"] == "Raspberry Pi Foundation"
    assert "MCU" in info["board_type"]


def test_info_unknown_board_returns_none(boards_dir):
    """info returns None for a nonexistent slug."""
    info = get_board_info("nonexistent-board-xyz", boards_dir)
    assert info is None


def test_info_includes_key_fields(boards_dir):
    """info includes processing, software, pricing fields."""
    info = get_board_info("esp32-s3-devkitc-1", boards_dir)
    assert info is not None
    assert "processing" in info
    assert "software" in info
    assert "pricing" in info


def test_info_cli_output(boards_dir):
    """CLI info displays formatted board details."""
    runner = CliRunner()
    result = runner.invoke(cli, ["info", "raspberry-pi-pico", "--boards-dir", str(boards_dir)])
    assert result.exit_code == 0
    assert "Raspberry Pi Pico" in result.output


def test_info_cli_unknown_board(boards_dir):
    """CLI info exits with error for unknown board."""
    runner = CliRunner()
    result = runner.invoke(cli, ["info", "nonexistent-board-xyz", "--boards-dir", str(boards_dir)])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()
