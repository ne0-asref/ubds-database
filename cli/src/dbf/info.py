"""Board info display."""

from pathlib import Path

from dbf.data import load_all_boards


def get_board_info(slug: str, boards_dir: Path) -> dict | None:
    """Get full board data by slug. Returns None if not found."""
    boards = load_all_boards(boards_dir)
    for board in boards:
        if board.get("slug") == slug:
            return board
    return None
