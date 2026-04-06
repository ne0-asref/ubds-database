"""Tests for board data fetching and caching."""

from unittest.mock import patch, MagicMock
from pathlib import Path

from dbf.data import find_boards_dir, load_board_file, StrDateLoader


def test_find_boards_dir_uses_local_first(boards_dir):
    """When boards/ exists locally, use it instead of fetching."""
    result = find_boards_dir(local_override=str(boards_dir))
    assert result == boards_dir


def test_find_boards_dir_returns_path(boards_dir):
    """find_boards_dir returns a Path object."""
    result = find_boards_dir(local_override=str(boards_dir))
    assert isinstance(result, Path)


def test_load_board_file(boards_dir):
    """load_board_file parses YAML with dates as strings."""
    board = load_board_file(boards_dir / "raspberry-pi-pico.ubds.yaml")
    assert board["name"] == "Raspberry Pi Pico"
    assert isinstance(board["slug"], str)
    # Dates should be strings, not datetime objects
    if "release_date" in board:
        assert isinstance(board["release_date"], str)


def test_str_date_loader():
    """StrDateLoader keeps YAML dates as strings."""
    import yaml
    content = "date: 2023-03-21"
    data = yaml.load(content, Loader=StrDateLoader)
    assert isinstance(data["date"], str)
    assert data["date"] == "2023-03-21"
