"""Additive iron-rule check (originally C22 U1).

Every board YAML under ``boards/`` must validate against the current
schema. If this test goes red, the schema has either broken the
additive-only promise (D22.3) or a board needs migration. Schema
additions must be loosened or the offending board promoted to a
documented edge case in CHANGELOG.md.

Originally written to cover the v1.1 → v1.2 transition. Now that all
boards declare 1.2, this is the standing regression check for any
future schema bump (v1.2 → v1.3, etc.).
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "spec" / "ubds-v1.schema.json"
BOARDS_DIR = REPO / "boards"


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _all_board_paths() -> list[Path]:
    return sorted(BOARDS_DIR.rglob("*.ubds.yaml"))


def test_boards_directory_is_non_empty():
    """Sanity check — if this fires, the parametrize below would silently pass."""
    paths = _all_board_paths()
    assert paths, f"no boards found under {BOARDS_DIR}"


@pytest.mark.parametrize("board_path", _all_board_paths(), ids=lambda p: p.name)
def test_existing_board_validates_under_v12_schema(board_path: Path):
    """Every board on disk validates against the current (v1.2) schema."""
    schema = _load_schema()
    data = yaml.safe_load(board_path.read_text(encoding="utf-8"))
    jsonschema.validate(data, schema)


def test_bundled_cli_schema_matches_canonical():
    """The bundled CLI copy must be byte-identical to the canonical schema."""
    canonical = SCHEMA_PATH.read_bytes()
    bundled = (REPO / "cli" / "src" / "dbf" / "data" / "ubds-v1.schema.json").read_bytes()
    assert canonical == bundled, (
        "spec/ubds-v1.schema.json and cli/src/dbf/data/ubds-v1.schema.json have "
        "diverged. Re-sync by copying the canonical file over the bundled copy."
    )


def test_ubds_version_pattern_stays_open():
    """Pattern must accept any 1.x release — D22.1 keeps the door open for v1.3."""
    schema = _load_schema()
    assert schema["properties"]["ubds_version"]["pattern"] == r"^1\.\d+$"
