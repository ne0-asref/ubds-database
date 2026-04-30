"""C22 U3 — board.manufacturer_slug ↔ manufacturers/<slug>.yaml link rule.

When a board declares ``manufacturer_slug:``, the validator confirms:

1. ``manufacturers/<manufacturer_slug>.yaml`` exists.
2. The board's ``manufacturer:`` field equals the manufacturer file's
   ``canonical_name`` OR is in its ``aliases`` (case-insensitive +
   whitespace-collapsed).

Boards without ``manufacturer_slug:`` are silently ignored — the field is
optional during the v1.1 → v1.2 transition window.
"""
from __future__ import annotations

from pathlib import Path

from dbf.validate import check_manufacturer_links


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _board(
    path: Path,
    *,
    slug: str,
    manufacturer: str,
    manufacturer_slug: str | None = None,
) -> Path:
    body = [
        'ubds_version: "1.2"',
        f'name: "{slug}"',
        f'slug: "{slug}"',
        f'manufacturer: "{manufacturer}"',
    ]
    if manufacturer_slug is not None:
        body.append(f'manufacturer_slug: "{manufacturer_slug}"')
    body += [
        "board_type:",
        "  - MCU",
        "meta:",
        "  sources:",
        '    - "https://example.com/datasheet"',
        '  product_url: "https://example.com/board"',
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return path


def _mfr(
    path: Path,
    *,
    slug: str,
    canonical_name: str,
    aliases: list[str] | None = None,
) -> Path:
    body = [f'slug: "{slug}"', f'canonical_name: "{canonical_name}"']
    if aliases is not None:
        body.append("aliases:")
        for a in aliases:
            body.append(f'  - "{a}"')
    body.append('homepage_url: "https://example.com/"')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------

def test_board_without_manufacturer_slug_is_ignored(tmp_path):
    (tmp_path / "boards").mkdir()
    _board(tmp_path / "boards" / "alpha.ubds.yaml",
           slug="alpha", manufacturer="Whoever")
    assert check_manufacturer_links(tmp_path) == []


def test_link_via_canonical_name_passes(tmp_path):
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()
    _mfr(tmp_path / "manufacturers" / "espressif.yaml",
         slug="espressif", canonical_name="Espressif Systems",
         aliases=["Espressif"])
    _board(tmp_path / "boards" / "espressif" / "esp32.ubds.yaml",
           slug="esp32", manufacturer="Espressif Systems",
           manufacturer_slug="espressif")
    assert check_manufacturer_links(tmp_path) == []


def test_link_via_alias_passes(tmp_path):
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()
    _mfr(tmp_path / "manufacturers" / "espressif.yaml",
         slug="espressif", canonical_name="Espressif Systems",
         aliases=["Espressif"])
    # Board uses alias name, not canonical.
    _board(tmp_path / "boards" / "espressif" / "esp32.ubds.yaml",
           slug="esp32", manufacturer="Espressif",
           manufacturer_slug="espressif")
    assert check_manufacturer_links(tmp_path) == []


def test_link_case_insensitive_whitespace_collapsed(tmp_path):
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()
    _mfr(tmp_path / "manufacturers" / "raspberry-pi.yaml",
         slug="raspberry-pi", canonical_name="Raspberry Pi Ltd",
         aliases=["Raspberry Pi", "Raspberry Pi Foundation"])
    # Board uses one of the aliases with funky whitespace.
    _board(tmp_path / "boards" / "raspberry-pi" / "rp2040-pico.ubds.yaml",
           slug="rp2040-pico", manufacturer="raspberry  pi  foundation",
           manufacturer_slug="raspberry-pi")
    assert check_manufacturer_links(tmp_path) == []


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------

def test_missing_manufacturer_yaml_rejected(tmp_path):
    """Spec.md §Tests: 'Board with `manufacturer_slug: espressif` validates
    ONLY if espressif.yaml exists with matching canonical_name'."""
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()  # exists but empty
    b = _board(tmp_path / "boards" / "esp32.ubds.yaml",
               slug="esp32", manufacturer="Espressif Systems",
               manufacturer_slug="espressif")
    errs = check_manufacturer_links(tmp_path)
    assert len(errs) == 1, [e.message for e in errs]
    assert "no matching manufacturers/espressif.yaml" in errs[0].message
    assert errs[0].board_path == b


def test_manufacturer_dir_absent_still_reports_when_slug_referenced(tmp_path):
    """Even if manufacturers/ doesn't exist, declared manufacturer_slug fails."""
    (tmp_path / "boards").mkdir()
    b = _board(tmp_path / "boards" / "esp32.ubds.yaml",
               slug="esp32", manufacturer="Espressif Systems",
               manufacturer_slug="espressif")
    errs = check_manufacturer_links(tmp_path)
    assert len(errs) == 1
    assert "no matching" in errs[0].message
    assert errs[0].board_path == b


def test_manufacturer_name_mismatch_rejected(tmp_path):
    """manufacturer_slug points at a real file but the board's manufacturer
    name doesn't match canonical_name or any alias → reject."""
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()
    _mfr(tmp_path / "manufacturers" / "espressif.yaml",
         slug="espressif", canonical_name="Espressif Systems",
         aliases=["Espressif"])
    b = _board(tmp_path / "boards" / "esp32.ubds.yaml",
               slug="esp32", manufacturer="Some Other Vendor",
               manufacturer_slug="espressif")
    errs = check_manufacturer_links(tmp_path)
    assert len(errs) == 1
    assert "does not match" in errs[0].message
    assert errs[0].board_path == b


def test_board_missing_manufacturer_field_rejected(tmp_path):
    """If a board declares manufacturer_slug but lacks the manufacturer
    field, the link rule still fires (to flag the broken record)."""
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()
    _mfr(tmp_path / "manufacturers" / "espressif.yaml",
         slug="espressif", canonical_name="Espressif Systems")
    p = tmp_path / "boards" / "esp32.ubds.yaml"
    p.write_text(
        'ubds_version: "1.2"\n'
        'name: "esp32"\n'
        'slug: "esp32"\n'
        'manufacturer_slug: "espressif"\n'
        "board_type:\n  - MCU\n"
        "meta:\n  sources:\n    - \"https://example.com/d\"\n"
        '  product_url: "https://example.com/b"\n',
        encoding="utf-8",
    )
    errs = check_manufacturer_links(tmp_path)
    assert any("missing the manufacturer field" in e.message for e in errs)


# ---------------------------------------------------------------------------
# Real-tree smoke
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_real_repo_link_clean():
    """No board today declares manufacturer_slug — link rule must be silent."""
    if not (REPO_ROOT / "boards").is_dir():
        import pytest
        pytest.skip("repo boards/ not present")
    errs = check_manufacturer_links(REPO_ROOT)
    assert errs == [], "\n".join(e.message for e in errs)
