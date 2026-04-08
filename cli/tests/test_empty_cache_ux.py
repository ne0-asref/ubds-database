"""Empty-cache UX: search/info should print a helpful message and exit 2."""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from dbf.cli import main


@pytest.fixture
def runner():
    return CliRunner(mix_stderr=False)


def _empty_boards_dir(tmp_path, monkeypatch):
    d = tmp_path / "empty-boards"
    d.mkdir()
    monkeypatch.setenv("DBF_BOARDS_DIR", str(d))
    return d


def test_search_empty_cache_prints_helpful_message(runner, tmp_path, monkeypatch):
    _empty_boards_dir(tmp_path, monkeypatch)
    r = runner.invoke(main, ["search", "--wifi"])
    assert r.exit_code == 2
    assert "Run `dbf cache update`" in (r.stderr or "")
    assert "No boards in local cache" in (r.stderr or "")


def test_info_empty_cache_prints_helpful_message(runner, tmp_path, monkeypatch):
    _empty_boards_dir(tmp_path, monkeypatch)
    r = runner.invoke(main, ["info", "esp32-s3-devkitc-1"])
    assert r.exit_code == 2
    assert "Run `dbf cache update`" in (r.stderr or "")
    assert "No boards in local cache" in (r.stderr or "")


def test_search_empty_cache_json_mode_returns_structured_error(runner, tmp_path, monkeypatch):
    _empty_boards_dir(tmp_path, monkeypatch)
    r = runner.invoke(main, ["search", "--wifi", "--json"])
    assert r.exit_code == 2
    payload = json.loads(r.stdout)
    assert payload["error"] == "empty_cache"
    assert "message" in payload


def test_info_empty_cache_json_mode_returns_structured_error(runner, tmp_path, monkeypatch):
    _empty_boards_dir(tmp_path, monkeypatch)
    r = runner.invoke(main, ["info", "esp32-s3-devkitc-1", "--json"])
    assert r.exit_code == 2
    payload = json.loads(r.stdout)
    assert payload["error"] == "empty_cache"
