"""SR1..SR20 — dbf search filter coverage."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dbf.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "cached_boards"


@pytest.fixture(autouse=True)
def _boards_dir(monkeypatch):
    monkeypatch.setenv("DBF_BOARDS_DIR", str(FIXTURES))


def _run(runner, *args):
    return runner.invoke(main, ["search", *args])


def _slugs(out: str) -> set[str]:
    return {s for s in ("alpha-board", "beta-board", "gamma-board") if s in out}


# SR1
def test_search_no_filters_returns_all(runner):
    r = _run(runner)
    assert r.exit_code == 0
    assert _slugs(r.output) == {"alpha-board", "beta-board", "gamma-board"}


# SR2
def test_search_wifi_filter(runner):
    r = _run(runner, "--wifi")
    assert r.exit_code == 0
    assert _slugs(r.output) == {"alpha-board"}


# SR3
def test_search_ble_filter(runner):
    r = _run(runner, "--ble")
    assert r.exit_code == 0
    assert _slugs(r.output) == {"alpha-board"}


# SR4
def test_search_lora_filter(runner):
    r = _run(runner, "--lora")
    assert r.exit_code == 0
    assert _slugs(r.output) == {"gamma-board"}


# SR5
def test_search_no_wireless_filter(runner):
    r = _run(runner, "--no-wireless")
    assert r.exit_code == 0
    assert _slugs(r.output) == {"beta-board"}


# SR6
def test_search_architecture_filter(runner):
    r = _run(runner, "--architecture", "ARM Cortex-M4")
    assert r.exit_code == 0
    assert _slugs(r.output) == {"alpha-board"}


# SR7
def test_search_ram_min(runner):
    r = _run(runner, "--ram-min", "256")
    assert r.exit_code == 0
    assert _slugs(r.output) == {"alpha-board", "gamma-board"}


# SR8
def test_search_ram_max(runner):
    r = _run(runner, "--ram-max", "100")
    assert r.exit_code == 0
    assert _slugs(r.output) == {"beta-board"}


# SR9
def test_search_clock_min(runner):
    r = _run(runner, "--clock-min", "200")
    assert r.exit_code == 0
    assert _slugs(r.output) == {"gamma-board"}


# SR12
def test_search_tag_filter(runner):
    r = _run(runner, "--tag", "iot")
    assert r.exit_code == 0
    assert _slugs(r.output) == {"alpha-board"}


# SR13
def test_search_use_case_filter(runner):
    r = _run(runner, "--use-case", "prototyping")
    assert r.exit_code == 0
    assert _slugs(r.output) == {"alpha-board", "beta-board"}


# SR14
def test_search_difficulty_filter(runner):
    r = _run(runner, "--difficulty", "advanced")
    assert r.exit_code == 0
    assert _slugs(r.output) == {"gamma-board"}


# SR15
def test_search_multi_filter_AND(runner):
    r = _run(runner, "--wifi", "--ble")
    assert r.exit_code == 0
    assert _slugs(r.output) == {"alpha-board"}


# SR16
def test_search_repeatable_flag_OR(runner):
    r = _run(runner, "--board-type", "MCU", "--board-type", "SBC")
    assert r.exit_code == 0
    assert _slugs(r.output) == {"alpha-board", "beta-board", "gamma-board"}


# SR17
def test_search_no_match_exits_0_with_message(runner):
    r = _run(runner, "--name", "zzznope")
    assert r.exit_code == 0
    assert "No boards match." in r.output


# SR18
def test_search_json_output_parses(runner):
    r = _run(runner, "--json")
    assert r.exit_code == 0
    data = json.loads(r.output)
    assert isinstance(data, list)
    assert len(data) == 3
    slugs = {b["slug"] for b in data}
    assert slugs == {"alpha-board", "beta-board", "gamma-board"}


# SR19
def test_search_default_table_columns(runner):
    r = _run(runner)
    assert r.exit_code == 0
    out = r.output
    assert "slug" in out
    assert "name" in out
    assert "manufacturer" in out
    assert "key specs" in out


# SR20 — meta drift guardrail
EXPECTED_FLAGS = [
    "--name",
    "--manufacturer",
    "--board-type",
    "--architecture",
    "--wifi",
    "--ble",
    "--lora",
    "--thread",
    "--zigbee",
    "--cellular",
    "--no-wireless",
    "--framework",
    "--language",
    "--ram-min",
    "--ram-max",
    "--flash-min",
    "--flash-max",
    "--clock-min",
    "--cores-min",
    "--tag",
    "--use-case",
    "--form-factor",
    "--difficulty",
    "--has-sensor",
    "--has-display",
    "--verified",
    "--community-reviewed",
    "--json",
]


def test_search_every_locked_flag_exists_in_help(runner):
    r = runner.invoke(main, ["search", "--help"])
    assert r.exit_code == 0
    missing = [f for f in EXPECTED_FLAGS if f not in r.output]
    assert not missing, f"missing flags in --help: {missing}"
