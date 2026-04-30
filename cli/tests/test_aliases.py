"""C22 U4 — within-batch alias-collision validator.

Tests :func:`dbf.validate.check_aliases`. Each test builds a synthetic
``boards/`` (and optionally ``manufacturers/``) tree under ``tmp_path``
then asserts the collision results name every colliding source.

Comparison rule: case-insensitive + whitespace-collapsed (e.g. ``"RPi 5"``
and ``"rpi5"`` collide).
"""
from __future__ import annotations

from pathlib import Path

from dbf.validate import check_aliases


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _board(path: Path, slug: str, *, aliases: list[str] | None = None) -> Path:
    body = [
        'ubds_version: "1.2"',
        f'name: "{slug}"',
        f'slug: "{slug}"',
        'manufacturer: "Test Co"',
        'board_type:',
        '  - MCU',
    ]
    if aliases is not None:
        body.append("aliases:")
        for a in aliases:
            body.append(f'  - "{a}"')
    body += [
        "meta:",
        "  sources:",
        '    - "https://example.com/datasheet"',
        '  product_url: "https://example.com/board"',
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return path


def _manufacturer(path: Path, slug: str, canonical_name: str) -> Path:
    body = [
        f'slug: "{slug}"',
        f'canonical_name: "{canonical_name}"',
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return path


def _msg_concat(results) -> str:
    return " || ".join(r.message for r in results)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------

def test_no_aliases_no_collision(tmp_path):
    """23 existing boards (none with aliases) → empty result."""
    (tmp_path / "boards").mkdir()
    _board(tmp_path / "boards" / "alpha.ubds.yaml", "alpha")
    _board(tmp_path / "boards" / "beta.ubds.yaml", "beta")
    assert check_aliases(tmp_path) == []


def test_distinct_aliases_no_collision(tmp_path):
    (tmp_path / "boards").mkdir()
    _board(tmp_path / "boards" / "alpha.ubds.yaml", "alpha", aliases=["A1"])
    _board(tmp_path / "boards" / "beta.ubds.yaml", "beta", aliases=["B1", "B2"])
    assert check_aliases(tmp_path) == []


def test_missing_boards_dir_returns_empty(tmp_path):
    """Caller may invoke against a tree without boards/ — graceful, not crash."""
    assert check_aliases(tmp_path) == []


# ---------------------------------------------------------------------------
# Spec test 1 — within-batch alias collision
# ---------------------------------------------------------------------------

def test_two_boards_share_alias_rejected_naming_both(tmp_path):
    """Two boards declare alias 'RPi 5' → reject, message names both files."""
    (tmp_path / "boards").mkdir()
    a = _board(tmp_path / "boards" / "raspberry-pi-5.ubds.yaml", "raspberry-pi-5", aliases=["RPi 5"])
    b = _board(tmp_path / "boards" / "rpi-5-clone.ubds.yaml", "rpi-5-clone", aliases=["RPi 5"])

    results = check_aliases(tmp_path)
    assert len(results) == 1, _msg_concat(results)
    msg = results[0].message
    assert str(a) in msg
    assert str(b) in msg
    assert {a, b} <= set(results[0].paths)


# ---------------------------------------------------------------------------
# Spec test 2 — alias matches existing board slug
# ---------------------------------------------------------------------------

def test_alias_matches_other_board_slug_rejected(tmp_path):
    (tmp_path / "boards").mkdir()
    a = _board(tmp_path / "boards" / "rpi5.ubds.yaml", "rpi5")
    b = _board(tmp_path / "boards" / "other.ubds.yaml", "other", aliases=["rpi5"])

    results = check_aliases(tmp_path)
    assert len(results) == 1, _msg_concat(results)
    msg = results[0].message
    assert str(a) in msg
    assert str(b) in msg


def test_alias_matches_other_board_alias_rejected(tmp_path):
    (tmp_path / "boards").mkdir()
    a = _board(tmp_path / "boards" / "alpha.ubds.yaml", "alpha", aliases=["shared-name"])
    b = _board(tmp_path / "boards" / "beta.ubds.yaml", "beta", aliases=["shared-name"])

    results = check_aliases(tmp_path)
    assert len(results) == 1
    assert {a, b} <= set(results[0].paths)


# ---------------------------------------------------------------------------
# Spec test 3 — alias matches manufacturer canonical_name / slug
# ---------------------------------------------------------------------------

def test_alias_matches_manufacturer_canonical_name_rejected(tmp_path):
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()
    b = _board(
        tmp_path / "boards" / "rpi5.ubds.yaml",
        "rpi5",
        aliases=["Raspberry Pi"],
    )
    m = _manufacturer(
        tmp_path / "manufacturers" / "raspberry-pi.yaml",
        "raspberry-pi",
        "Raspberry Pi",
    )

    results = check_aliases(tmp_path)
    assert len(results) == 1, _msg_concat(results)
    msg = results[0].message
    assert str(b) in msg
    assert str(m) in msg


def test_alias_matches_manufacturer_slug_rejected(tmp_path):
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()
    b = _board(
        tmp_path / "boards" / "alpha.ubds.yaml",
        "alpha",
        aliases=["espressif"],
    )
    m = _manufacturer(
        tmp_path / "manufacturers" / "espressif.yaml",
        "espressif",
        "Espressif Systems",
    )

    results = check_aliases(tmp_path)
    assert len(results) == 1, _msg_concat(results)
    assert {b, m} <= set(results[0].paths)


# ---------------------------------------------------------------------------
# Spec test 4 — case-insensitive + whitespace-collapsed match
# ---------------------------------------------------------------------------

def test_case_insensitive_whitespace_collapse(tmp_path):
    """'RPi 5' and 'rpi5' must be treated as the same alias."""
    (tmp_path / "boards").mkdir()
    a = _board(tmp_path / "boards" / "alpha.ubds.yaml", "alpha", aliases=["RPi 5"])
    b = _board(tmp_path / "boards" / "beta.ubds.yaml", "beta", aliases=["rpi5"])

    results = check_aliases(tmp_path)
    assert len(results) == 1, _msg_concat(results)
    assert {a, b} <= set(results[0].paths)


def test_mixed_whitespace_kinds_collapse(tmp_path):
    """Tabs, multiple spaces, leading/trailing whitespace all collapse."""
    (tmp_path / "boards").mkdir()
    a = _board(tmp_path / "boards" / "alpha.ubds.yaml", "alpha", aliases=["Foo  Bar"])
    b = _board(tmp_path / "boards" / "beta.ubds.yaml", "beta", aliases=["  foo\tbar  "])

    results = check_aliases(tmp_path)
    assert len(results) == 1, _msg_concat(results)
    assert {a, b} <= set(results[0].paths)


# ---------------------------------------------------------------------------
# Robustness — slug-only collisions are NOT this rule (rule 13 handles them)
# ---------------------------------------------------------------------------

def test_two_board_slugs_only_not_flagged_here(tmp_path):
    """Slug-vs-slug collision is rule 13's job, not the alias check.

    The alias check only fires when at least one of the colliding sources is
    an alias entry (or alias-equivalent: manufacturer canonical_name).
    """
    (tmp_path / "boards").mkdir()
    _board(tmp_path / "boards" / "a.ubds.yaml", "shared")
    _board(tmp_path / "boards" / "b.ubds.yaml", "shared")
    assert check_aliases(tmp_path) == []


def test_two_manufacturer_canonical_names_collision_flagged(tmp_path):
    """Two manufacturers with the same canonical_name → that's an alias-equivalent
    collision (the canonical_name acts as the manufacturer's primary alias)."""
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()
    a = _manufacturer(
        tmp_path / "manufacturers" / "espressif.yaml",
        "espressif",
        "Espressif",
    )
    b = _manufacturer(
        tmp_path / "manufacturers" / "espressif-systems.yaml",
        "espressif-systems",
        "Espressif",
    )
    results = check_aliases(tmp_path)
    assert len(results) == 1, _msg_concat(results)
    assert {a, b} <= set(results[0].paths)


# ---------------------------------------------------------------------------
# Robustness — malformed input does not crash
# ---------------------------------------------------------------------------

def test_unparseable_yaml_skipped(tmp_path):
    (tmp_path / "boards").mkdir()
    _board(tmp_path / "boards" / "alpha.ubds.yaml", "alpha", aliases=["shared"])
    (tmp_path / "boards" / "broken.ubds.yaml").write_text(
        "not: valid: yaml: [\n", encoding="utf-8",
    )
    # Should not raise; the unparseable file is skipped.
    results = check_aliases(tmp_path)
    assert results == []


def test_nested_boards_layout_walked(tmp_path):
    """Boards under boards/<mfr>/<slug>.ubds.yaml are also walked (U2 layout)."""
    (tmp_path / "boards" / "raspberry-pi").mkdir(parents=True)
    (tmp_path / "boards" / "espressif").mkdir(parents=True)
    a = _board(
        tmp_path / "boards" / "raspberry-pi" / "rpi5.ubds.yaml",
        "rpi5", aliases=["dual"],
    )
    b = _board(
        tmp_path / "boards" / "espressif" / "esp32.ubds.yaml",
        "esp32", aliases=["dual"],
    )
    results = check_aliases(tmp_path)
    assert len(results) == 1
    assert {a, b} <= set(results[0].paths)
