"""C22 U2 — filesystem nesting migration: validator path-walker.

Verifies that:

- :func:`dbf.validate.collect_paths` discovers boards under both the legacy
  flat layout (``boards/<slug>.ubds.yaml``) and the new nested layout
  (``boards/<manufacturer-slug>/<slug>.ubds.yaml``) in one pass.
- :func:`dbf.validate.find_flat_layout_files` correctly distinguishes the
  two layouts so the CLI can emit the deprecation warning exactly when a
  flat-layout file is still present in the canonical tree.
- The cross-file slug-uniqueness rule (C21 Rule 13) keeps firing across
  the nested tree — slug identity is unchanged by the layout move.
- :func:`dbf.vendor_map.slug_for_manufacturer` derives the directory slug
  for known canonical names and falls back to ``"unknown"`` for unmapped
  vendors per ubds-spec-revision-handoff §5.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from dbf import vendor_map
from dbf.validate import (
    FLAT_LAYOUT_DEPRECATION,
    check_images,
    collect_paths,
    find_flat_layout_files,
    is_flat_layout_board,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BOARD_TEMPLATE = """\
ubds_version: "1.2"
name: "{slug}"
slug: "{slug}"
manufacturer: "Test Co"
board_type:
  - MCU
meta:
  sources:
    - "https://example.com/datasheet"
  product_url: "https://example.com/board"
"""


def _write_board(path: Path, slug: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_BOARD_TEMPLATE.format(slug=slug), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# slug_for_manufacturer
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name, expected",
    [
        ("Espressif Systems", "espressif"),
        ("Adafruit Industries", "adafruit-industries"),
        ("Raspberry Pi Foundation", "raspberry-pi"),
        ("Raspberry Pi Ltd", "raspberry-pi"),  # both legal names → same slug
        ("NVIDIA", "nvidia"),
        ("STMicroelectronics", "st"),
        ("Seeed Studio", "seeed"),
        ("Lattice Semiconductor", "lattice"),
        ("Nordic Semiconductor", "nordic"),
        ("NXP Semiconductors", "nxp"),
        ("BeagleBoard.org Foundation", "beagleboard"),
        ("Arduino", "arduino"),
        # Aliases route through normalize_vendor → canonical → slug.
        ("Adafruit", "adafruit-industries"),
        ("Espressif", "espressif"),
        ("ST", "st"),
        # Whitespace tolerance.
        ("  NVIDIA  ", "nvidia"),
    ],
)
def test_slug_for_manufacturer_known(name, expected):
    assert vendor_map.slug_for_manufacturer(name) == expected


@pytest.mark.parametrize(
    "name",
    ["", "   ", "WeAct Studio", "PJRC", "Particle Industries", "made-up vendor"],
)
def test_slug_for_manufacturer_unknown_falls_back(name):
    assert vendor_map.slug_for_manufacturer(name) == vendor_map.UNKNOWN_MANUFACTURER_SLUG
    assert vendor_map.UNKNOWN_MANUFACTURER_SLUG == "unknown"


def test_slug_for_manufacturer_non_string_returns_unknown():
    assert vendor_map.slug_for_manufacturer(None) == "unknown"
    assert vendor_map.slug_for_manufacturer(123) == "unknown"


# ---------------------------------------------------------------------------
# collect_paths walks both layouts
# ---------------------------------------------------------------------------

def test_collect_paths_walks_flat_layout(tmp_path):
    boards = tmp_path / "boards"
    a = _write_board(boards / "alpha.ubds.yaml", "alpha")
    b = _write_board(boards / "beta.ubds.yaml", "beta")
    found = collect_paths(str(boards))
    assert set(found) == {a, b}


def test_collect_paths_walks_nested_layout(tmp_path):
    boards = tmp_path / "boards"
    a = _write_board(boards / "espressif" / "esp32.ubds.yaml", "esp32")
    b = _write_board(boards / "raspberry-pi" / "rp2040-pico.ubds.yaml", "rp2040-pico")
    found = collect_paths(str(boards))
    assert set(found) == {a, b}


def test_collect_paths_walks_both_layouts_together(tmp_path):
    """Mixed tree (transition window) — flat + nested files all surface."""
    boards = tmp_path / "boards"
    flat = _write_board(boards / "legacy.ubds.yaml", "legacy")
    nested = _write_board(boards / "espressif" / "esp32.ubds.yaml", "esp32")
    unknown = _write_board(boards / "unknown" / "weird.ubds.yaml", "weird")
    found = collect_paths(str(boards))
    assert set(found) == {flat, nested, unknown}


def test_collect_paths_single_file_returns_only_that_file(tmp_path):
    boards = tmp_path / "boards"
    a = _write_board(boards / "espressif" / "esp32.ubds.yaml", "esp32")
    found = collect_paths(str(a))
    assert found == [a]


# ---------------------------------------------------------------------------
# Flat-layout deprecation detection
# ---------------------------------------------------------------------------

def test_is_flat_layout_board_recognizes_flat(tmp_path):
    boards = tmp_path / "boards"
    flat = _write_board(boards / "alpha.ubds.yaml", "alpha")
    assert is_flat_layout_board(flat, boards) is True


def test_is_flat_layout_board_recognizes_nested(tmp_path):
    boards = tmp_path / "boards"
    nested = _write_board(boards / "espressif" / "esp32.ubds.yaml", "esp32")
    assert is_flat_layout_board(nested, boards) is False


def test_is_flat_layout_board_outside_boards_root(tmp_path):
    """A file completely outside boards_root should not be flagged."""
    other = tmp_path / "tests" / "fixture.ubds.yaml"
    other.parent.mkdir(parents=True)
    other.write_text("slug: x\n")
    assert is_flat_layout_board(other, tmp_path / "boards") is False


def test_find_flat_layout_files_only_flat_when_dir_has_both(tmp_path):
    boards = tmp_path / "boards"
    flat = _write_board(boards / "legacy.ubds.yaml", "legacy")
    _write_board(boards / "espressif" / "esp32.ubds.yaml", "esp32")
    paths = collect_paths(str(boards))
    flat_files = find_flat_layout_files(str(boards), paths)
    assert flat_files == [flat]


def test_find_flat_layout_files_repo_root_arg(tmp_path):
    """Caller passing the repo root (parent of boards/) still gets flagged."""
    (tmp_path / "boards").mkdir()
    flat = _write_board(tmp_path / "boards" / "legacy.ubds.yaml", "legacy")
    _write_board(tmp_path / "boards" / "espressif" / "esp32.ubds.yaml", "esp32")
    paths = collect_paths(str(tmp_path / "boards"))
    flat_files = find_flat_layout_files(str(tmp_path), paths)
    assert flat_files == [flat]


def test_find_flat_layout_files_empty_when_all_nested(tmp_path):
    boards = tmp_path / "boards"
    _write_board(boards / "espressif" / "esp32.ubds.yaml", "esp32")
    _write_board(boards / "raspberry-pi" / "rp2040-pico.ubds.yaml", "rp2040-pico")
    paths = collect_paths(str(boards))
    assert find_flat_layout_files(str(boards), paths) == []


def test_find_flat_layout_files_single_file_invocation_silent(tmp_path):
    """A single-file invocation outside the canonical tree should not warn."""
    one_off = tmp_path / "scratch" / "weird.ubds.yaml"
    one_off.parent.mkdir(parents=True)
    one_off.write_text("slug: weird\n", encoding="utf-8")
    assert find_flat_layout_files(str(one_off), [one_off]) == []


def test_find_flat_layout_files_handles_arg_not_a_dir(tmp_path):
    """Glob args (string passed as a glob pattern) shouldn't crash."""
    boards = tmp_path / "boards"
    _write_board(boards / "alpha.ubds.yaml", "alpha")
    paths = collect_paths(str(boards / "*.ubds.yaml"))
    # str(boards / "*.ubds.yaml") is neither a dir nor a file -> empty list.
    assert find_flat_layout_files(str(boards / "*.ubds.yaml"), paths) == []


# ---------------------------------------------------------------------------
# Slug-uniqueness rule survives the move (C21 Rule 13)
# ---------------------------------------------------------------------------

def test_duplicate_slug_across_manufacturer_dirs_still_rejected(tmp_path):
    """Two boards with the same slug in different mfr dirs is still illegal.

    C21 Rule 13 — globally unique slug across the tree — survives the U2
    layout move. The violation surfaces as one consolidated ``duplicate
    slug`` error that names both files (rendered as the bare filenames so
    contributors can grep their working tree).
    """
    boards = tmp_path / "boards"
    a = _write_board(boards / "espressif" / "shared-slug.ubds.yaml", "shared-slug")
    b = _write_board(boards / "nvidia" / "shared-slug.ubds.yaml", "shared-slug")
    (tmp_path / "images").mkdir()  # check_images expects images/ alongside

    results = check_images(tmp_path)
    dup_errors = [r for r in results if "duplicate slug" in r.message]
    assert len(dup_errors) == 1
    msg = dup_errors[0].message
    assert "shared-slug" in msg
    # Both files are named in the message, even though they live in
    # different manufacturer subdirectories.
    assert a.name in msg
    assert b.name in msg


def test_nested_layout_no_duplicate_passes(tmp_path):
    """Distinct nested boards — no duplicate-slug errors."""
    boards = tmp_path / "boards"
    _write_board(boards / "espressif" / "esp32-c6.ubds.yaml", "esp32-c6")
    _write_board(boards / "raspberry-pi" / "rp2040-pico.ubds.yaml", "rp2040-pico")
    (tmp_path / "images").mkdir()

    results = check_images(tmp_path)
    assert [r for r in results if "duplicate slug" in r.message] == []


# ---------------------------------------------------------------------------
# CLI deprecation-warning wiring
# ---------------------------------------------------------------------------

def test_cli_warning_emitted_for_flat_layout(tmp_path, runner):
    from dbf.cli import main

    boards = tmp_path / "boards"
    _write_board(boards / "alpha.ubds.yaml", "alpha")
    r = runner.invoke(main, ["validate", str(boards)])
    assert r.exit_code == 0, r.output
    # Click captures stderr into r.stderr when mix_stderr=False; the runner
    # used in conftest mixes them, so the warning surfaces in r.output.
    assert FLAT_LAYOUT_DEPRECATION in r.output


def test_cli_no_warning_for_nested_layout(tmp_path, runner):
    from dbf.cli import main

    boards = tmp_path / "boards"
    _write_board(boards / "espressif" / "esp32.ubds.yaml", "esp32")
    _write_board(boards / "raspberry-pi" / "rp2040-pico.ubds.yaml", "rp2040-pico")
    r = runner.invoke(main, ["validate", str(boards)])
    assert r.exit_code == 0, r.output
    assert FLAT_LAYOUT_DEPRECATION not in r.output


def test_cli_warning_present_for_mixed_layout(tmp_path, runner):
    from dbf.cli import main

    boards = tmp_path / "boards"
    _write_board(boards / "legacy.ubds.yaml", "legacy")
    _write_board(boards / "espressif" / "esp32.ubds.yaml", "esp32")
    r = runner.invoke(main, ["validate", str(boards)])
    assert r.exit_code == 0, r.output
    assert FLAT_LAYOUT_DEPRECATION in r.output
    assert "1 file(s) still at flat layout" in r.output


# ---------------------------------------------------------------------------
# Real-tree smoke — the migrated repo itself has zero flat-layout boards
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_real_repo_has_no_flat_layout_boards():
    """Sanity check: after the U2 migration the repo's own boards/ is fully nested."""
    boards = REPO_ROOT / "boards"
    if not boards.is_dir():
        pytest.skip("repo boards/ not present")
    flat = [p for p in boards.glob("*.ubds.yaml") if p.is_file()]
    assert flat == [], f"expected zero flat-layout boards, found {flat}"


def test_real_repo_boards_all_nested_and_count_at_least_23():
    """Every board YAML should now live under boards/<mfr>/<slug>.ubds.yaml."""
    boards = REPO_ROOT / "boards"
    if not boards.is_dir():
        pytest.skip("repo boards/ not present")
    nested = sorted(p for p in boards.rglob("*.ubds.yaml") if p.is_file())
    # ≥ 23 leaves room for future additions; spec requires the existing 23.
    assert len(nested) >= 23, f"expected ≥ 23 nested boards, got {len(nested)}"
    for p in nested:
        rel = p.relative_to(boards)
        assert len(rel.parts) == 2, f"{p} not in boards/<mfr>/<slug>.ubds.yaml shape"
