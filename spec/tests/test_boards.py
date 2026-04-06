"""Validate all board YAML files against the UBDS v1 JSON Schema."""

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

SCHEMA_PATH = Path(__file__).parent.parent / "ubds-v1.schema.json"
BOARDS_DIR = Path(__file__).parent.parent.parent / "boards"

# Custom YAML loader that keeps dates as strings (YAML auto-parses dates)
class StrDateLoader(yaml.SafeLoader):
    pass

StrDateLoader.add_constructor(
    "tag:yaml.org,2002:timestamp",
    lambda loader, node: loader.construct_scalar(node),
)


@pytest.fixture(scope="module")
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def board_files():
    """Discover all .ubds.yaml files in boards/."""
    files = sorted(BOARDS_DIR.glob("*.ubds.yaml"))
    return files


def board_ids():
    return [f.stem.replace(".ubds", "") for f in board_files()]


class TestBoardDatabase:
    """Validate every board file in boards/."""

    def test_board_directory_exists(self):
        assert BOARDS_DIR.is_dir(), f"boards/ directory not found at {BOARDS_DIR}"

    def test_at_least_15_boards(self):
        files = board_files()
        assert len(files) >= 15, f"Expected >= 15 boards, found {len(files)}"

    @pytest.mark.parametrize("board_file", board_files(), ids=board_ids())
    def test_board_validates_against_schema(self, schema, board_file):
        with open(board_file) as f:
            board = yaml.load(f, Loader=StrDateLoader)
        jsonschema.validate(board, schema)

    @pytest.mark.parametrize("board_file", board_files(), ids=board_ids())
    def test_board_slug_matches_filename(self, board_file):
        with open(board_file) as f:
            board = yaml.load(f, Loader=StrDateLoader)
        expected_slug = board_file.stem.replace(".ubds", "")
        assert board["slug"] == expected_slug, (
            f"slug '{board['slug']}' doesn't match filename '{expected_slug}'"
        )

    @pytest.mark.parametrize("board_file", board_files(), ids=board_ids())
    def test_board_has_meta_sources(self, board_file):
        with open(board_file) as f:
            board = yaml.load(f, Loader=StrDateLoader)
        assert "meta" in board, "Board must have meta section"
        assert "sources" in board["meta"], "meta must have sources"
        assert len(board["meta"]["sources"]) >= 1, "meta.sources must have >= 1 URL"

    def test_all_slugs_unique(self):
        slugs = []
        for bf in board_files():
            with open(bf) as f:
                board = yaml.load(f, Loader=StrDateLoader)
            slugs.append(board["slug"])
        assert len(slugs) == len(set(slugs)), f"Duplicate slugs found: {[s for s in slugs if slugs.count(s) > 1]}"
