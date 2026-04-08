"""Tests V1..V18 for ``dbf validate`` (Task 4)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from dbf.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def _copy(name: str, dest: Path) -> Path:
    target = dest / name
    shutil.copy(FIXTURES / name, target)
    return target


# ---------- happy paths ----------

def test_validate_valid_minimal_exits_0(runner):
    r = runner.invoke(main, ["validate", str(FIXTURES / "valid-minimal.ubds.yaml")])
    assert r.exit_code == 0, r.output


def test_validate_valid_full_exits_0(runner):
    r = runner.invoke(main, ["validate", str(FIXTURES / "valid-full.ubds.yaml")])
    assert r.exit_code == 0, r.output


# ---------- error paths ----------

def test_validate_missing_name_exits_1(runner):
    r = runner.invoke(main, ["validate", str(FIXTURES / "invalid-missing-name.ubds.yaml")])
    assert r.exit_code == 1
    assert "name" in r.output
    assert "\u2717" in r.output


def test_validate_bad_enum_exits_1(runner):
    r = runner.invoke(main, ["validate", str(FIXTURES / "invalid-bad-enum.ubds.yaml")])
    assert r.exit_code == 1
    assert "board_type" in r.output
    assert "FAKE" in r.output


def test_validate_wrong_type_exits_1(runner):
    r = runner.invoke(main, ["validate", str(FIXTURES / "invalid-wrong-type.ubds.yaml")])
    assert r.exit_code == 1
    assert "clock_mhz" in r.output
    assert "string" in r.output


def test_validate_bad_slug_exits_1(runner):
    r = runner.invoke(main, ["validate", str(FIXTURES / "invalid-bad-slug.ubds.yaml")])
    assert r.exit_code == 1
    assert "slug" in r.output
    assert "pattern" in r.output.lower()


# ---------- path expansion ----------

def test_validate_directory_walks_files(runner, tmp_path):
    d = tmp_path / "boards"
    d.mkdir()
    _copy("valid-minimal.ubds.yaml", d)
    _copy("valid-full.ubds.yaml", d)
    r = runner.invoke(main, ["validate", str(d)])
    assert r.exit_code == 0
    assert "valid-minimal" in r.output
    assert "valid-full" in r.output


def test_validate_glob(runner):
    pattern = str(FIXTURES / "invalid-*.ubds.yaml")
    r = runner.invoke(main, ["validate", pattern])
    assert r.exit_code == 1
    # Multiple invalid fixtures should be referenced
    assert r.output.count("\u2717") >= 2


# ---------- json output ----------

def test_validate_json_flag(runner):
    r = runner.invoke(main, [
        "validate",
        "--json",
        str(FIXTURES / "invalid-missing-name.ubds.yaml"),
    ])
    assert r.exit_code == 1
    data = json.loads(r.output)
    assert isinstance(data, list)
    assert data[0]["file"].endswith("invalid-missing-name.ubds.yaml")
    assert any("name" in e["message"] or e["path"] == "name" for e in data[0]["errors"])
    for e in data[0]["errors"]:
        for k in ("path", "message", "line", "col", "fix"):
            assert k in e


# ---------- --fix tests ----------

def test_validate_fix_lowercases_protocol(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_FIX_ASSUME_YES", "1")
    f = _copy("invalid-uppercase-protocol.ubds.yaml", tmp_path)
    r = runner.invoke(main, ["validate", "--fix", str(f)])
    text = f.read_text()
    assert "WiFi" not in text
    assert "wifi" in text
    bak = f.with_suffix(f.suffix + ".bak")
    assert bak.exists()
    assert "WiFi" in bak.read_text()
    assert r.exit_code == 0


def test_validate_fix_normalizes_mfr(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_FIX_ASSUME_YES", "1")
    f = _copy("invalid-uppercase-mfr.ubds.yaml", tmp_path)
    r = runner.invoke(main, ["validate", "--fix", str(f)])
    text = f.read_text()
    assert "STMicroelectronics" in text
    assert r.exit_code == 0


def test_validate_fix_strips_trailing_whitespace(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_FIX_ASSUME_YES", "1")
    f = _copy("invalid-trailing-ws.ubds.yaml", tmp_path)
    runner.invoke(main, ["validate", "--fix", str(f)])
    for line in f.read_text().splitlines():
        assert line == line.rstrip()


def test_validate_fix_converts_tabs(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_FIX_ASSUME_YES", "1")
    f = _copy("invalid-tabs.ubds.yaml", tmp_path)
    r = runner.invoke(main, ["validate", "--fix", str(f)])
    text = f.read_text()
    assert "\t" not in text
    assert r.exit_code == 0


def test_validate_fix_does_not_touch_slugs(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_FIX_ASSUME_YES", "1")
    f = _copy("invalid-bad-slug.ubds.yaml", tmp_path)
    r = runner.invoke(main, ["validate", "--fix", str(f)])
    assert "Bad Slug" in f.read_text()
    assert r.exit_code == 1  # still invalid


def test_validate_fix_does_not_touch_dates(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_FIX_ASSUME_YES", "1")
    src = tmp_path / "ambig-date.ubds.yaml"
    src.write_text(
        'ubds_version: "1.0"\n'
        'name: "Date Board"\n'
        'slug: "date-board"\n'
        'manufacturer: "Test Co"\n'
        'board_type:\n  - MCU\n'
        'release_date: "March 21, 2023"\n'
        'meta:\n  sources:\n    - "https://example.com/datasheet"\n'
    )
    runner.invoke(main, ["validate", "--fix", str(src)])
    assert "March 21, 2023" in src.read_text()


def test_validate_fix_creates_bak_file(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_FIX_ASSUME_YES", "1")
    f = _copy("invalid-uppercase-mfr.ubds.yaml", tmp_path)
    runner.invoke(main, ["validate", "--fix", str(f)])
    bak = f.with_suffix(f.suffix + ".bak")
    assert bak.exists()
    assert '"ST"' in bak.read_text()


def test_validate_fix_idempotent(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("DBF_FIX_ASSUME_YES", "1")
    f = _copy("invalid-uppercase-protocol.ubds.yaml", tmp_path)
    runner.invoke(main, ["validate", "--fix", str(f)])
    after_first = f.read_text()
    runner.invoke(main, ["validate", "--fix", str(f)])
    after_second = f.read_text()
    assert after_first == after_second


def test_legacy_pricing_block_rejected(runner, tmp_path):
    f = tmp_path / "with-pricing.ubds.yaml"
    f.write_text(
        'ubds_version: "1.1"\n'
        'name: "Priced Board"\n'
        'slug: "priced-board"\n'
        'manufacturer: "Test Co"\n'
        'board_type:\n  - MCU\n'
        'pricing:\n  msrp_usd: 10\n'
        'meta:\n'
        '  sources:\n    - "https://example.com/datasheet"\n'
        '  product_url: "https://example.com/board"\n',
        encoding="utf-8",
    )
    r = runner.invoke(main, ["validate", str(f)])
    assert r.exit_code == 1
    assert "pricing" in r.output


def test_missing_product_url_rejected(runner, tmp_path):
    f = tmp_path / "no-product.ubds.yaml"
    f.write_text(
        'ubds_version: "1.1"\n'
        'name: "No Product Board"\n'
        'slug: "no-product-board"\n'
        'manufacturer: "Test Co"\n'
        'board_type:\n  - MCU\n'
        'meta:\n'
        '  sources:\n    - "https://example.com/datasheet"\n',
        encoding="utf-8",
    )
    r = runner.invoke(main, ["validate", str(f)])
    assert r.exit_code == 1
    assert "product_url" in r.output


def test_non_uri_product_url_rejected(runner, tmp_path):
    f = tmp_path / "bad-product.ubds.yaml"
    f.write_text(
        'ubds_version: "1.1"\n'
        'name: "Bad Product Board"\n'
        'slug: "bad-product-board"\n'
        'manufacturer: "Test Co"\n'
        'board_type:\n  - MCU\n'
        'meta:\n'
        '  sources:\n    - "https://example.com/datasheet"\n'
        '  product_url: "not a url"\n',
        encoding="utf-8",
    )
    r = runner.invoke(main, ["validate", str(f)])
    assert r.exit_code == 1
    lowered = r.output.lower()
    assert "product_url" in r.output or "uri" in lowered


def test_validate_exit_code_aggregates(runner, tmp_path):
    d = tmp_path / "mixed"
    d.mkdir()
    _copy("valid-minimal.ubds.yaml", d)
    _copy("invalid-missing-name.ubds.yaml", d)
    r = runner.invoke(main, ["validate", str(d)])
    assert r.exit_code == 1
