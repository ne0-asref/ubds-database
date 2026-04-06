"""Tests for dbf search functionality."""

from pathlib import Path

from click.testing import CliRunner

from dbf.cli import cli
from dbf.search import search_boards, load_boards


def test_search_wifi_filter(boards_dir):
    """--wifi flag returns only boards with WiFi wireless."""
    boards = load_boards(boards_dir)
    results = search_boards(boards, wifi=True)
    assert len(results) > 0
    for board in results:
        wireless_protocols = [
            w.get("protocol", "").lower() for w in board.get("wireless", [])
        ]
        assert "wifi" in wireless_protocols, f"{board['slug']} has no WiFi"


def test_search_rust_filter(boards_dir):
    """--rust flag returns boards with Rust language support."""
    boards = load_boards(boards_dir)
    results = search_boards(boards, rust=True)
    assert len(results) > 0
    for board in results:
        languages = [
            l.get("name", "").lower()
            for l in board.get("software", {}).get("languages", [])
        ]
        assert "rust" in languages, f"{board['slug']} has no Rust"


def test_search_wifi_and_rust(boards_dir):
    """--wifi --rust returns only boards with both."""
    boards = load_boards(boards_dir)
    results = search_boards(boards, wifi=True, rust=True)
    assert len(results) > 0
    for board in results:
        wireless = [w.get("protocol", "").lower() for w in board.get("wireless", [])]
        langs = [l.get("name", "").lower() for l in board.get("software", {}).get("languages", [])]
        assert "wifi" in wireless
        assert "rust" in langs


def test_search_no_matches(boards_dir):
    """Search with impossible filter combination returns empty list."""
    boards = load_boards(boards_dir)
    results = search_boards(boards, architecture="nonexistent_arch_xyz")
    assert results == []


def test_search_by_manufacturer(boards_dir):
    """--manufacturer filters by manufacturer name (case-insensitive)."""
    boards = load_boards(boards_dir)
    results = search_boards(boards, manufacturer="raspberry pi")
    assert len(results) > 0
    for board in results:
        assert "raspberry pi" in board["manufacturer"].lower()


def test_search_by_board_type(boards_dir):
    """--type filters by board_type."""
    boards = load_boards(boards_dir)
    results = search_boards(boards, board_type="SBC")
    assert len(results) > 0
    for board in results:
        assert "SBC" in board["board_type"]


def test_search_by_architecture(boards_dir):
    """--architecture filters by CPU architecture substring."""
    boards = load_boards(boards_dir)
    results = search_boards(boards, architecture="cortex-m4")
    assert len(results) > 0


def test_search_cli_output(boards_dir):
    """CLI search outputs board names."""
    runner = CliRunner()
    result = runner.invoke(cli, ["search", "--boards-dir", str(boards_dir), "--wifi"])
    assert result.exit_code == 0
    assert len(result.output.strip()) > 0


def test_search_cli_no_results(boards_dir):
    """CLI search with no matches shows message."""
    runner = CliRunner()
    result = runner.invoke(cli, ["search", "--boards-dir", str(boards_dir), "--architecture", "nonexistent_xyz"])
    assert result.exit_code == 0
    assert "no boards" in result.output.lower() or result.output.strip() == ""
