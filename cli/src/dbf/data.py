"""Board data loading and caching."""

from pathlib import Path

import yaml


class StrDateLoader(yaml.SafeLoader):
    """YAML loader that keeps dates as strings instead of datetime objects."""
    pass


StrDateLoader.add_constructor(
    "tag:yaml.org,2002:timestamp",
    lambda loader, node: loader.construct_scalar(node),
)


def find_boards_dir(local_override: str | None = None) -> Path:
    """Find the boards directory.

    Priority:
    1. Explicit local_override path
    2. boards/ relative to CWD
    3. ~/.devboardfinder/boards/ (cached from GitHub)
    """
    if local_override:
        p = Path(local_override)
        if p.is_dir():
            return p

    # Check relative to CWD
    cwd_boards = Path.cwd() / "boards"
    if cwd_boards.is_dir():
        return cwd_boards

    # Check cache directory
    cache_dir = Path.home() / ".devboardfinder" / "boards"
    if cache_dir.is_dir():
        return cache_dir

    # Return the CWD path even if it doesn't exist — caller handles missing
    return cwd_boards


def load_board_file(path: Path) -> dict:
    """Load a single UBDS YAML board file, keeping dates as strings."""
    with open(path) as f:
        return yaml.load(f, Loader=StrDateLoader)


def load_all_boards(boards_dir: Path) -> list[dict]:
    """Load all .ubds.yaml files from a directory."""
    boards = []
    for f in sorted(boards_dir.glob("*.ubds.yaml")):
        try:
            board = load_board_file(f)
            if board:
                boards.append(board)
        except Exception:
            continue
    return boards
