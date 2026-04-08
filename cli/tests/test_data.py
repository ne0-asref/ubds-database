"""Tests for cache + GitHub tree-API auto-fetch (D1..D17)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
import responses

from dbf import cli, data


REPO = data.REPO
BRANCH = data.BRANCH
TREE_URL = f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"


def _raw_url(path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{path}"


def _yaml_bytes(slug: str) -> bytes:
    return (
        f'ubds_version: "1.0"\n'
        f"slug: {slug}\n"
        f"name: {slug.title()}\n"
        f"manufacturer: vendor\n"
        f"board_type:\n  - MCU\n"
        f"meta:\n  sources:\n    - https://example.com/{slug}\n"
    ).encode()


def _tree_payload(paths: list[str], extras: list[dict] | None = None) -> dict:
    tree = [{"path": p, "type": "blob", "sha": "x", "url": "u"} for p in paths]
    if extras:
        tree.extend(extras)
    return {"sha": "deadbeef", "tree": tree, "truncated": False}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(data.time, "sleep", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _no_token(monkeypatch):
    monkeypatch.delenv("DBF_REPO_TOKEN", raising=False)


# ---------- D1, D2 ----------

def test_cache_dir_default_is_under_home(monkeypatch, tmp_path):
    monkeypatch.delenv("DBF_CACHE_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    d = data.cache_dir()
    assert d == tmp_path / ".devboardfinder" / "boards"
    assert d.exists()


def test_cache_dir_overridable_by_env(monkeypatch, tmp_path):
    target = tmp_path / "custom-cache"
    monkeypatch.setenv("DBF_CACHE_DIR", str(target))
    assert data.cache_dir() == target
    assert target.exists()


# ---------- D3, D4, D5 ----------

@responses.activate
def test_cache_empty_triggers_fetch(tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    responses.add(responses.GET, TREE_URL,
                  json=_tree_payload(["boards/a.ubds.yaml"]), status=200)
    responses.add(responses.GET, _raw_url("boards/a.ubds.yaml"),
                  body=_yaml_bytes("a"), status=200)

    data.ensure_cache()

    assert (data.cache_dir() / "a.ubds.yaml").exists()
    assert len(responses.calls) == 2


@responses.activate
def test_cache_24h_fresh_skips_fetch(tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    d = data.cache_dir()
    (d / "x.ubds.yaml").write_bytes(_yaml_bytes("x"))
    # mtime is "now" → fresh
    data.ensure_cache()
    assert len(responses.calls) == 0


@responses.activate
def test_cache_25h_old_triggers_refetch(tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    d = data.cache_dir()
    stale = d / "old.ubds.yaml"
    stale.write_bytes(_yaml_bytes("old"))
    old_t = time.time() - (25 * 3600)
    os.utime(stale, (old_t, old_t))

    responses.add(responses.GET, TREE_URL,
                  json=_tree_payload(["boards/new.ubds.yaml"]), status=200)
    responses.add(responses.GET, _raw_url("boards/new.ubds.yaml"),
                  body=_yaml_bytes("new"), status=200)

    data.ensure_cache()
    assert (d / "new.ubds.yaml").exists()
    assert len(responses.calls) == 2


# ---------- D6, D7, D8 ----------

@responses.activate
def test_cache_update_force_ignores_timer(tmp_path, monkeypatch, runner):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    d = data.cache_dir()
    (d / "fresh.ubds.yaml").write_bytes(_yaml_bytes("fresh"))  # fresh!

    responses.add(responses.GET, TREE_URL,
                  json=_tree_payload(["boards/forced.ubds.yaml"]), status=200)
    responses.add(responses.GET, _raw_url("boards/forced.ubds.yaml"),
                  body=_yaml_bytes("forced"), status=200)

    result = runner.invoke(cli.main, ["cache", "update"])
    assert result.exit_code == 0, result.output
    assert len(responses.calls) == 2
    assert (d / "forced.ubds.yaml").exists()


def test_cache_clear_deletes_dir(tmp_path, monkeypatch, runner):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    d = data.cache_dir()
    (d / "a.ubds.yaml").write_bytes(_yaml_bytes("a"))
    assert d.exists()
    result = runner.invoke(cli.main, ["cache", "clear"])
    assert result.exit_code == 0
    assert "cleared" in result.output
    assert not (tmp_path / "c").exists() or not any((tmp_path / "c").iterdir())


def test_cache_info_prints_age_and_count(tmp_path, monkeypatch, runner):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    d = data.cache_dir()
    (d / "a.ubds.yaml").write_bytes(_yaml_bytes("a"))
    (d / "b.ubds.yaml").write_bytes(_yaml_bytes("b"))
    result = runner.invoke(cli.main, ["cache", "info"])
    assert result.exit_code == 0
    assert "boards: 2" in result.output
    assert "last fetched:" in result.output
    assert "age:" in result.output


# ---------- D9, D10, D11 ----------

@responses.activate
def test_fetch_uses_tree_api_then_raw_url(tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    responses.add(responses.GET, TREE_URL,
                  json=_tree_payload(["boards/a.ubds.yaml", "boards/b.ubds.yaml"]),
                  status=200)
    responses.add(responses.GET, _raw_url("boards/a.ubds.yaml"),
                  body=_yaml_bytes("a"), status=200)
    responses.add(responses.GET, _raw_url("boards/b.ubds.yaml"),
                  body=_yaml_bytes("b"), status=200)

    data.fetch_boards()

    assert responses.calls[0].request.url.startswith(
        f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}")
    urls = {c.request.url for c in responses.calls[1:]}
    assert _raw_url("boards/a.ubds.yaml") in urls
    assert _raw_url("boards/b.ubds.yaml") in urls


@responses.activate
def test_fetch_anonymous_no_auth_header(tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    monkeypatch.delenv("DBF_REPO_TOKEN", raising=False)
    responses.add(responses.GET, TREE_URL,
                  json=_tree_payload(["boards/a.ubds.yaml"]), status=200)
    responses.add(responses.GET, _raw_url("boards/a.ubds.yaml"),
                  body=_yaml_bytes("a"), status=200)
    data.fetch_boards()
    for call in responses.calls:
        assert "Authorization" not in call.request.headers


@responses.activate
def test_fetch_with_token_sets_bearer(tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    monkeypatch.setenv("DBF_REPO_TOKEN", "secrettoken")
    responses.add(responses.GET, TREE_URL,
                  json=_tree_payload(["boards/a.ubds.yaml"]), status=200)
    responses.add(responses.GET, _raw_url("boards/a.ubds.yaml"),
                  body=_yaml_bytes("a"), status=200)
    data.fetch_boards()
    for call in responses.calls:
        assert call.request.headers.get("Authorization") == "Bearer secrettoken"


# ---------- D12, D13, D14, D15 ----------

@responses.activate
def test_fetch_5xx_retries_3_times_with_backoff(tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    responses.add(responses.GET, TREE_URL, status=503)
    responses.add(responses.GET, TREE_URL, status=503)
    responses.add(responses.GET, TREE_URL,
                  json=_tree_payload(["boards/a.ubds.yaml"]), status=200)
    responses.add(responses.GET, _raw_url("boards/a.ubds.yaml"),
                  body=_yaml_bytes("a"), status=200)

    data.fetch_boards()
    # 3 tree calls + 1 raw call
    tree_calls = [c for c in responses.calls if "git/trees" in c.request.url]
    assert len(tree_calls) == 3


@responses.activate
def test_fetch_persistent_5xx_falls_back_to_stale_cache(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    d = data.cache_dir()
    stale = d / "old.ubds.yaml"
    stale.write_bytes(_yaml_bytes("old"))
    old_t = time.time() - (25 * 3600)
    os.utime(stale, (old_t, old_t))

    for _ in range(3):
        responses.add(responses.GET, TREE_URL, status=503)

    data.ensure_cache()  # should not raise
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()
    assert stale.exists()


@responses.activate
def test_fetch_persistent_5xx_no_cache_clean_error(tmp_path, monkeypatch, runner):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    for _ in range(3):
        responses.add(responses.GET, TREE_URL, status=503)

    result = runner.invoke(cli.main, ["cache", "update"])
    assert result.exit_code == 1
    assert "error" in result.output.lower() or "error" in (result.stderr or "").lower() or "503" in result.output
    # no traceback
    assert "Traceback" not in result.output


@responses.activate
def test_fetch_404_clean_error(tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    responses.add(responses.GET, TREE_URL, status=404)
    with pytest.raises(data.FetchError) as ei:
        data.fetch_boards()
    assert "404" in str(ei.value) or "not reachable" in str(ei.value).lower()


# ---------- D16, D17 ----------

@responses.activate
def test_fetch_writes_files_atomically(tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    responses.add(responses.GET, TREE_URL,
                  json=_tree_payload(["boards/a.ubds.yaml"]), status=200)
    responses.add(responses.GET, _raw_url("boards/a.ubds.yaml"),
                  body=_yaml_bytes("a"), status=200)
    data.fetch_boards()
    d = data.cache_dir()
    leftover = list(d.glob("*.tmp"))
    assert leftover == []
    assert (d / "a.ubds.yaml").exists()


@responses.activate
def test_cache_only_yaml_files_written(tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_CACHE_DIR", str(tmp_path / "c"))
    extras = [
        {"path": "README.md", "type": "blob"},
        {"path": "boards/.gitkeep", "type": "blob"},
        {"path": "boards/notes.txt", "type": "blob"},
        {"path": "spec/ubds.schema.json", "type": "blob"},
    ]
    responses.add(responses.GET, TREE_URL,
                  json=_tree_payload(["boards/a.ubds.yaml"], extras=extras),
                  status=200)
    responses.add(responses.GET, _raw_url("boards/a.ubds.yaml"),
                  body=_yaml_bytes("a"), status=200)

    data.fetch_boards()
    files = sorted(p.name for p in data.cache_dir().iterdir())
    assert files == ["a.ubds.yaml"]
