"""Tests for `dbf info <slug>`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dbf.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "cached_boards"


@pytest.fixture(autouse=True)
def _boards_dir(monkeypatch):
    monkeypatch.setenv("DBF_BOARDS_DIR", str(FIXTURES))


def test_info_known_slug_renders(runner):
    r = runner.invoke(main, ["info", "alpha-board"])
    assert r.exit_code == 0, r.output
    out = r.output
    assert "Alpha" in out
    assert "Vendor A" in out
    assert "ARM Cortex-M4" in out
    assert "wifi" in out
    assert "ble" in out


def test_info_unknown_slug_clean_error(runner):
    r = runner.invoke(main, ["info", "nonexistent"])
    assert r.exit_code == 1
    combined = (r.output or "") + (r.stderr if r.stderr_bytes else "")
    assert "nonexistent" in combined
    assert "Traceback" not in combined


def test_info_json_flag(runner):
    r = runner.invoke(main, ["info", "alpha-board", "--json"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert isinstance(data, dict)
    assert data["slug"] == "alpha-board"
    assert data["name"] == "Alpha"
    assert data["manufacturer"] == "Vendor A"


def test_info_raw_flag(runner):
    r = runner.invoke(main, ["info", "alpha-board", "--raw"])
    assert r.exit_code == 0, r.output
    raw_text = (FIXTURES / "alpha-board.ubds.yaml").read_text(encoding="utf-8")
    assert raw_text.strip() in r.output


def test_info_includes_freshness_indicator(runner):
    r = runner.invoke(main, ["info", "alpha-board"])
    assert r.exit_code == 0, r.output
    assert "2026-03-01" in r.output


def test_info_corrupt_yaml_clean_error(runner, tmp_path, monkeypatch):
    bad = tmp_path / "broken-board.ubds.yaml"
    bad.write_text("name: [unclosed\n  bad: : :\n", encoding="utf-8")
    monkeypatch.setenv("DBF_BOARDS_DIR", str(tmp_path))
    r = runner.invoke(main, ["info", "broken-board"])
    assert r.exit_code == 1
    combined = (r.output or "") + (r.stderr if r.stderr_bytes else "")
    assert "error" in combined.lower()
    assert "broken-board" in combined
    assert "Traceback" not in combined


def test_info_does_not_render_pricing_line(runner):
    r = runner.invoke(main, ["info", "alpha-board"])
    assert r.exit_code == 0, r.output
    assert "pricing:" not in r.output
