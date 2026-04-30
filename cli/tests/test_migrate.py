"""C22 U6 — ``dbf migrate`` v1.1 → v1.2 tests.

Covers the behaviour locked in ``artifacts/build/U6/spec.md``:

- v1.1 file gains ``aliases: []`` + ``manufacturer_slug:`` + version bump.
- Idempotent: ``migrate(migrate(x)) == migrate(x)`` byte-for-byte.
- Comments preserved (line-preserving string edits — no ``yaml.dump``).
- Pre-write ``validate_file`` gate: existing schema violations abort.
- ``--nest-by-manufacturer`` moves flat-layout boards under
  ``boards/<manufacturer-slug>/``.
- Dry-run by default; ``--in-place`` actually writes.
- v1.0 file emits the "v1.0 → v1.1 not implemented" sentinel and does
  not corrupt the file on disk.
- Whole-tree smoke: ``dbf migrate boards/`` runs across all 23 real
  boards and the post-migrate state still validates.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from dbf import migrate as _migrate
from dbf import validate as _validate
from dbf.cli import main as cli_main


REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Pure-function unit tests (T1)
# ---------------------------------------------------------------------------


V11_MINIMAL_WITH_COMMENTS = """\
ubds_version: "1.1"
# canonical name verified against vendor homepage
name: "Test Board"
slug: "test-board"
manufacturer: Espressif Systems  # short alias also accepted by vendor_map
board_type:
  - MCU
meta:
  sources:
    - "https://example.com/test-board"
  product_url: "https://example.com/test-board"
"""


def test_add_aliases_inserts_when_missing():
    new_text, changed = _migrate.add_aliases(V11_MINIMAL_WITH_COMMENTS)
    assert changed is True
    assert "\naliases: []\n" in new_text
    # Inserted right after ubds_version: ... line.
    lines = new_text.splitlines()
    idx_version = next(i for i, l in enumerate(lines) if l.startswith("ubds_version:"))
    assert lines[idx_version + 1] == "aliases: []"


def test_add_aliases_is_noop_when_present():
    text = "ubds_version: \"1.1\"\naliases: [\"Foo\"]\nname: x\n"
    new_text, changed = _migrate.add_aliases(text)
    assert changed is False
    assert new_text == text


def test_add_manufacturer_slug_inserts_known_vendor():
    new_text, slug = _migrate.add_manufacturer_slug(V11_MINIMAL_WITH_COMMENTS)
    assert slug == "espressif"
    lines = new_text.splitlines()
    idx_mfr = next(i for i, l in enumerate(lines) if l.startswith("manufacturer:"))
    assert lines[idx_mfr + 1] == "manufacturer_slug: espressif"


def test_add_manufacturer_slug_noop_when_present():
    text = (
        "ubds_version: \"1.1\"\n"
        "manufacturer: Espressif Systems\n"
        "manufacturer_slug: espressif\n"
    )
    new_text, slug = _migrate.add_manufacturer_slug(text)
    assert slug is None
    assert new_text == text


def test_add_manufacturer_slug_unknown_vendor_does_not_insert():
    """Unknown vendors fall through to ``unknown`` slug — but the
    spec says manufacturer_slug should only be set when vendor_map
    resolves. ``unknown`` is not a real resolution; we leave the field
    unset so a contributor can add it explicitly."""
    text = (
        "ubds_version: \"1.1\"\n"
        "manufacturer: Some Random Co Ltd\n"
        "name: x\n"
    )
    new_text, slug = _migrate.add_manufacturer_slug(text)
    assert slug is None
    assert "manufacturer_slug" not in new_text


def test_bump_version_only_when_v12_field_present():
    # No v1.2 fields -> no bump.
    plain = "ubds_version: \"1.1\"\nname: x\n"
    out, changed = _migrate.bump_version_if_v12(plain)
    assert changed is False
    assert out == plain

    # aliases present -> bump.
    with_aliases = "ubds_version: \"1.1\"\naliases: []\nname: x\n"
    out, changed = _migrate.bump_version_if_v12(with_aliases)
    assert changed is True
    assert out.startswith("ubds_version: \"1.2\"\n")

    # manufacturer_slug present -> bump.
    with_slug = "ubds_version: \"1.1\"\nmanufacturer_slug: espressif\nname: x\n"
    out, changed = _migrate.bump_version_if_v12(with_slug)
    assert changed is True
    assert out.startswith("ubds_version: \"1.2\"\n")


def test_bump_version_preserves_quoting_style():
    # Single-quoted.
    sq = "ubds_version: '1.1'\naliases: []\n"
    out, _ = _migrate.bump_version_if_v12(sq)
    assert out.startswith("ubds_version: '1.2'\n")
    # Bare.
    bare = "ubds_version: 1.1\naliases: []\n"
    out, _ = _migrate.bump_version_if_v12(bare)
    assert out.startswith("ubds_version: 1.2\n")


def test_migrate_text_full_v11_to_v12():
    new_text, report = _migrate.migrate_text(V11_MINIMAL_WITH_COMMENTS)
    assert report.skipped_reason is None
    assert report.aborted is False
    # All three transforms applied.
    assert "aliases: []" in new_text
    assert "manufacturer_slug: espressif" in new_text
    assert new_text.startswith("ubds_version: \"1.2\"\n")
    # Comments survived.
    assert "# canonical name verified against vendor homepage" in new_text
    assert "# short alias also accepted by vendor_map" in new_text
    # Original ubds_version "1.1" line is gone.
    assert "ubds_version: \"1.1\"" not in new_text


def test_migrate_text_idempotent_byte_for_byte():
    once, _ = _migrate.migrate_text(V11_MINIMAL_WITH_COMMENTS)
    twice, report = _migrate.migrate_text(once)
    assert twice == once
    assert report.changes == []  # second run reports no changes


def test_migrate_text_v10_emits_sentinel_and_does_not_transform():
    text = "ubds_version: \"1.0\"\nname: x\nmanufacturer: Espressif\n"
    new_text, report = _migrate.migrate_text(text)
    assert new_text == text
    assert report.skipped_reason is not None
    assert "1.0" in report.skipped_reason


# ---------------------------------------------------------------------------
# File-level migrate (T2)
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_v11_file(tmp_path):
    """A v1.1 board file on disk for migrate_file tests."""
    p = tmp_path / "test-board.ubds.yaml"
    p.write_text(V11_MINIMAL_WITH_COMMENTS, encoding="utf-8")
    return p


def test_migrate_file_dry_run_does_not_write(tmp_v11_file):
    original = tmp_v11_file.read_text(encoding="utf-8")
    report = _migrate.migrate_file(tmp_v11_file, in_place=False)
    assert report.written is False
    assert report.changes  # has planned changes
    assert tmp_v11_file.read_text(encoding="utf-8") == original


def test_migrate_file_in_place_writes(tmp_v11_file):
    report = _migrate.migrate_file(tmp_v11_file, in_place=True)
    assert report.written is True
    on_disk = tmp_v11_file.read_text(encoding="utf-8")
    assert "aliases: []" in on_disk
    assert "manufacturer_slug: espressif" in on_disk
    assert on_disk.startswith("ubds_version: \"1.2\"\n")


def test_migrate_file_aborts_on_existing_schema_violation(tmp_path):
    """A pre-existing schema violation must abort the migrate before any
    write — otherwise we'd happily mass-bump versions on broken files."""
    bad = tmp_path / "broken.ubds.yaml"
    bad.write_text(
        "ubds_version: \"1.1\"\n"
        # missing required fields: name, slug, manufacturer, board_type, meta
        "manufacturer_slug: espressif\n",
        encoding="utf-8",
    )
    original = bad.read_text(encoding="utf-8")
    report = _migrate.migrate_file(bad, in_place=True)
    assert report.aborted is True
    assert report.written is False
    assert bad.read_text(encoding="utf-8") == original


def test_migrate_file_v10_does_not_corrupt(tmp_path):
    p = tmp_path / "v10.ubds.yaml"
    text = (
        "ubds_version: \"1.0\"\n"
        "name: x\n"
        "slug: x\n"
        "manufacturer: Espressif\n"
        "board_type: [MCU]\n"
        "meta:\n"
        "  sources: [\"https://example.com\"]\n"
        "  product_url: \"https://example.com\"\n"
    )
    p.write_text(text, encoding="utf-8")
    report = _migrate.migrate_file(p, in_place=True)
    assert report.skipped_reason is not None
    assert p.read_text(encoding="utf-8") == text  # untouched


def test_migrate_file_idempotent_on_disk(tmp_v11_file):
    _migrate.migrate_file(tmp_v11_file, in_place=True)
    after_first = tmp_v11_file.read_text(encoding="utf-8")
    _migrate.migrate_file(tmp_v11_file, in_place=True)
    after_second = tmp_v11_file.read_text(encoding="utf-8")
    assert after_first == after_second


# ---------------------------------------------------------------------------
# --nest-by-manufacturer (T3)
# ---------------------------------------------------------------------------


def test_nest_flat_layout_file_moves_under_manufacturer(tmp_path):
    boards = tmp_path / "boards"
    boards.mkdir()
    flat = boards / "test-board.ubds.yaml"
    flat.write_text(V11_MINIMAL_WITH_COMMENTS, encoding="utf-8")

    dest = _migrate.nest_file(flat, boards, in_place=True)
    expected = boards / "espressif" / "test-board.ubds.yaml"
    assert dest == expected
    assert expected.exists()
    assert not flat.exists()


def test_nest_already_nested_is_noop(tmp_path):
    boards = tmp_path / "boards"
    nested_dir = boards / "espressif"
    nested_dir.mkdir(parents=True)
    nested = nested_dir / "test-board.ubds.yaml"
    nested.write_text(V11_MINIMAL_WITH_COMMENTS, encoding="utf-8")

    dest = _migrate.nest_file(nested, boards, in_place=True)
    assert dest is None
    assert nested.exists()


def test_nest_unknown_manufacturer_falls_through_to_unknown(tmp_path):
    boards = tmp_path / "boards"
    boards.mkdir()
    flat = boards / "weird.ubds.yaml"
    flat.write_text(
        "ubds_version: \"1.1\"\n"
        "name: x\n"
        "slug: weird\n"
        "manufacturer: Mystery Corp\n"
        "board_type: [MCU]\n"
        "meta:\n"
        "  sources: [\"https://example.com\"]\n"
        "  product_url: \"https://example.com\"\n",
        encoding="utf-8",
    )
    dest = _migrate.nest_file(flat, boards, in_place=True)
    assert dest == boards / "unknown" / "weird.ubds.yaml"
    assert dest.exists()


def test_nest_dry_run_returns_destination_without_moving(tmp_path):
    boards = tmp_path / "boards"
    boards.mkdir()
    flat = boards / "test-board.ubds.yaml"
    flat.write_text(V11_MINIMAL_WITH_COMMENTS, encoding="utf-8")
    dest = _migrate.nest_file(flat, boards, in_place=False)
    assert dest == boards / "espressif" / "test-board.ubds.yaml"
    assert flat.exists()
    assert not dest.exists()


# ---------------------------------------------------------------------------
# CLI wiring (T4)
# ---------------------------------------------------------------------------


def test_cli_migrate_help_lists_both_flags(runner):
    result = runner.invoke(cli_main, ["migrate", "--help"])
    assert result.exit_code == 0
    assert "--in-place" in result.output
    assert "--nest-by-manufacturer" in result.output


def test_cli_migrate_default_dry_run(runner, tmp_path):
    p = tmp_path / "test-board.ubds.yaml"
    p.write_text(V11_MINIMAL_WITH_COMMENTS, encoding="utf-8")
    original = p.read_text(encoding="utf-8")
    result = runner.invoke(cli_main, ["migrate", str(p)])
    assert result.exit_code == 0
    assert p.read_text(encoding="utf-8") == original
    # Dry-run announces the planned changes.
    assert "would" in result.output.lower() or "dry" in result.output.lower()


def test_cli_migrate_in_place_writes(runner, tmp_path):
    p = tmp_path / "test-board.ubds.yaml"
    p.write_text(V11_MINIMAL_WITH_COMMENTS, encoding="utf-8")
    result = runner.invoke(cli_main, ["migrate", str(p), "--in-place"])
    assert result.exit_code == 0, result.output
    on_disk = p.read_text(encoding="utf-8")
    assert "aliases: []" in on_disk
    assert "manufacturer_slug: espressif" in on_disk


def test_cli_migrate_directory_walks_yaml_files(runner, tmp_path):
    boards = tmp_path / "boards"
    sub = boards / "espressif"
    sub.mkdir(parents=True)
    p = sub / "test-board.ubds.yaml"
    p.write_text(V11_MINIMAL_WITH_COMMENTS, encoding="utf-8")
    # Sanity-check directory walking (default dry-run).
    result = runner.invoke(cli_main, ["migrate", str(boards)])
    assert result.exit_code == 0
    assert "test-board.ubds.yaml" in result.output


def test_cli_migrate_nest_flag_moves_files(runner, tmp_path):
    boards = tmp_path / "boards"
    boards.mkdir()
    flat = boards / "test-board.ubds.yaml"
    flat.write_text(V11_MINIMAL_WITH_COMMENTS, encoding="utf-8")
    result = runner.invoke(
        cli_main,
        ["migrate", str(boards), "--in-place", "--nest-by-manufacturer"],
    )
    assert result.exit_code == 0, result.output
    moved = boards / "espressif" / "test-board.ubds.yaml"
    assert moved.exists()
    assert not flat.exists()


# ---------------------------------------------------------------------------
# Whole-tree smoke (T5)
# ---------------------------------------------------------------------------


def test_migrate_runs_across_full_boards_tree(tmp_path):
    """Copy the real boards/ tree to a temp dir, run migrate against
    every file, and confirm each file still validates afterwards.

    Uses tmp_path so the canonical tree on disk is never mutated.
    """
    src = REPO_ROOT / "boards"
    if not src.is_dir():
        pytest.skip("boards/ not present in this checkout")
    dest = tmp_path / "boards"
    # Copy only the YAML tree (no images/, no README, etc.).
    import shutil
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("README.md"))

    yaml_files = sorted(dest.rglob("*.ubds.yaml"))
    assert len(yaml_files) >= 1

    aborted = []
    for f in yaml_files:
        report = _migrate.migrate_file(f, in_place=True)
        if report.aborted:
            aborted.append(f)

    # Migrate must not abort on any real board (they all validate today).
    assert aborted == []

    # Post-migrate: every file still validates.
    for f in yaml_files:
        result = _validate.validate_file(f)
        assert not result.errors, f"{f}: {[e.message for e in result.errors]}"
        assert result.parse_error is None, f"{f}: {result.parse_error}"
