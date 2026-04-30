"""C22 U3 — manufacturers/ index schema + directory-scoped validation.

Covers:

- Every seeded ``manufacturers/<slug>.yaml`` validates against
  ``ubds-manufacturer.schema.json``.
- Schema rejects malformed slug shapes (``Espressif``, ``raspberrypi_5``).
- Filename stem must equal the ``slug`` field.
- Cross-file alias collisions across two manufacturer YAMLs are reported,
  naming both files (this is the spec.md "Cross-file alias collision" V-gate).
- Add-criterion: a manufacturer without any referencing board AND without
  ``well_known: true`` is rejected.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from dbf.schema import load_manufacturer_schema
from dbf.validate import check_aliases, validate_manufacturers


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_mfr(
    path: Path,
    *,
    slug: str,
    canonical_name: str,
    homepage_url: str = "https://example.com/",
    aliases: list[str] | None = None,
    well_known: bool | None = None,
    country_code: str | None = None,
    extra_lines: list[str] | None = None,
) -> Path:
    body = [f'slug: "{slug}"', f'canonical_name: "{canonical_name}"']
    if aliases is not None:
        body.append("aliases:")
        for a in aliases:
            body.append(f'  - "{a}"')
    body.append(f'homepage_url: "{homepage_url}"')
    if country_code is not None:
        body.append(f'country_code: "{country_code}"')
    if well_known is not None:
        body.append(f'well_known: {"true" if well_known else "false"}')
    if extra_lines:
        body.extend(extra_lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return path


def _write_board(path: Path, slug: str, manufacturer: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'ubds_version: "1.2"\n'
        f'name: "{slug}"\n'
        f'slug: "{slug}"\n'
        f'manufacturer: "{manufacturer}"\n'
        "board_type:\n"
        "  - MCU\n"
        "meta:\n"
        "  sources:\n"
        '    - "https://example.com/datasheet"\n'
        '  product_url: "https://example.com/board"\n',
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Schema shape
# ---------------------------------------------------------------------------

def test_load_manufacturer_schema_returns_dict_with_expected_id():
    schema = load_manufacturer_schema()
    assert isinstance(schema, dict)
    assert schema.get("title", "").startswith("UBDS Manufacturer Index")
    assert schema["required"] == ["slug", "canonical_name", "homepage_url"]


@pytest.mark.parametrize(
    "slug",
    ["espressif", "raspberry-pi", "adafruit-industries", "st", "wch", "ti"],
)
def test_schema_accepts_kebab_case_slug(slug):
    Draft7Validator(load_manufacturer_schema()).validate({
        "slug": slug,
        "canonical_name": "X",
        "homepage_url": "https://example.com/",
    })


@pytest.mark.parametrize(
    "bad_slug",
    [
        "Espressif",        # uppercase
        "raspberrypi_5",    # underscore
        "raspberry pi",     # whitespace
        "-leading-hyphen",  # leading hyphen
        "trailing-hyphen-", # trailing hyphen
        "double--hyphen",   # consecutive hyphens
        "",                 # empty
    ],
)
def test_schema_rejects_bad_slug(bad_slug):
    validator = Draft7Validator(load_manufacturer_schema())
    errs = list(validator.iter_errors({
        "slug": bad_slug,
        "canonical_name": "X",
        "homepage_url": "https://example.com/",
    }))
    # Either pattern or minLength catches it; both count.
    assert errs


def test_schema_rejects_unknown_property():
    """``additionalProperties: false`` keeps the index minimal."""
    validator = Draft7Validator(load_manufacturer_schema())
    errs = list(validator.iter_errors({
        "slug": "x",
        "canonical_name": "X",
        "homepage_url": "https://example.com/",
        "wat": "nope",
    }))
    assert any(e.validator == "additionalProperties" for e in errs)


# ---------------------------------------------------------------------------
# Real-tree seed validates
# ---------------------------------------------------------------------------

def test_real_repo_manufacturers_dir_exists():
    mfr = REPO_ROOT / "manufacturers"
    if not mfr.is_dir():
        pytest.skip("manufacturers/ not present (running outside ubds-database)")
    files = sorted(mfr.glob("*.yaml"))
    # Spec: at least 14 well-known + per-distinct-vendor in boards/.
    assert len(files) >= 14, f"expected >= 14 manufacturer files, got {len(files)}"


def test_real_repo_seed_validates_clean():
    if not (REPO_ROOT / "manufacturers").is_dir():
        pytest.skip("manufacturers/ not present")
    errors = validate_manufacturers(REPO_ROOT)
    assert errors == [], "\n".join(e.message for e in errors)


def test_real_repo_well_knowns_have_flag():
    """The 14 vendors named in the C22 spec-revision handoff §6 must carry
    ``well_known: true``. The list also exercises the slug → canonical mapping."""
    expected = {
        "espressif", "adafruit-industries", "arduino", "raspberry-pi",
        "nordic", "st", "nxp", "sipeed", "seeed", "wch", "lattice",
        "beagleboard", "renesas", "ti",
    }
    mfr = REPO_ROOT / "manufacturers"
    if not mfr.is_dir():
        pytest.skip("manufacturers/ not present")
    import yaml as _yaml
    for slug in expected:
        f = mfr / f"{slug}.yaml"
        assert f.is_file(), f"missing well-known seed: {f}"
        data = _yaml.safe_load(f.read_text(encoding="utf-8"))
        assert data.get("well_known") is True, f"{slug} missing well_known: true"


# ---------------------------------------------------------------------------
# Directory-scoped rules — synthetic fixtures
# ---------------------------------------------------------------------------

def test_filename_stem_must_equal_slug(tmp_path):
    (tmp_path / "manufacturers").mkdir()
    _write_mfr(
        tmp_path / "manufacturers" / "renamed.yaml",
        slug="not-renamed", canonical_name="X", well_known=True,
    )
    errs = validate_manufacturers(tmp_path)
    assert any("slug field mismatch" in e.message for e in errs), [e.message for e in errs]


def test_duplicate_slug_across_files_rejected(tmp_path):
    (tmp_path / "manufacturers").mkdir()
    a = _write_mfr(
        tmp_path / "manufacturers" / "a.yaml",
        slug="dup", canonical_name="A", well_known=True,
    )
    # Force a same-slug second file via filename stem mismatch first.
    b = _write_mfr(
        tmp_path / "manufacturers" / "dup.yaml",
        slug="dup", canonical_name="B", well_known=True,
    )
    errs = validate_manufacturers(tmp_path)
    msgs = "\n".join(e.message for e in errs)
    assert "duplicate manufacturer slug" in msgs
    # First file ('a.yaml') has slug-mismatch, second ('dup.yaml') is the dup hit.
    assert str(a) in msgs or str(b) in msgs


def test_cross_file_alias_collision_rejected_naming_both(tmp_path):
    """Two manufacturer YAMLs sharing an alias → reject, name both files.

    Spec.md §Tests: 'Cross-file alias collision: 2 mfr YAMLs share alias →
    reject, name both'.
    """
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()
    a = _write_mfr(
        tmp_path / "manufacturers" / "alpha.yaml",
        slug="alpha", canonical_name="Alpha Corp",
        aliases=["Shared Alias"], well_known=True,
    )
    b = _write_mfr(
        tmp_path / "manufacturers" / "beta.yaml",
        slug="beta", canonical_name="Beta Inc",
        aliases=["Shared Alias"], well_known=True,
    )
    results = check_aliases(tmp_path)
    assert len(results) == 1, [r.message for r in results]
    msg = results[0].message
    assert str(a) in msg
    assert str(b) in msg
    assert {a, b} <= set(results[0].paths)


def test_cross_file_alias_collision_case_and_whitespace_insensitive(tmp_path):
    (tmp_path / "manufacturers").mkdir()
    a = _write_mfr(
        tmp_path / "manufacturers" / "alpha.yaml",
        slug="alpha", canonical_name="Alpha Corp",
        aliases=["Foo  Bar"], well_known=True,
    )
    b = _write_mfr(
        tmp_path / "manufacturers" / "beta.yaml",
        slug="beta", canonical_name="Beta Inc",
        aliases=["foobar"], well_known=True,
    )
    results = check_aliases(tmp_path)
    assert len(results) == 1, [r.message for r in results]
    assert {a, b} <= set(results[0].paths)


def test_self_record_slug_equals_canonical_is_not_collision(tmp_path):
    """A single mfr file whose slug matches its canonical_name (after
    case-fold + whitespace-collapse) must NOT count as a collision —
    that's the same record talking about itself.
    """
    (tmp_path / "manufacturers").mkdir()
    _write_mfr(
        tmp_path / "manufacturers" / "arduino.yaml",
        slug="arduino", canonical_name="Arduino", well_known=True,
    )
    assert check_aliases(tmp_path) == []


# ---------------------------------------------------------------------------
# Add-criterion: orphan manufacturer (no board, not well-known)
# ---------------------------------------------------------------------------

def test_orphan_manufacturer_rejected(tmp_path):
    """New manufacturer with no referencing board AND no well_known flag → reject."""
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()
    _write_mfr(
        tmp_path / "manufacturers" / "nobody.yaml",
        slug="nobody", canonical_name="Nobody",
    )
    errs = validate_manufacturers(tmp_path)
    assert any("orphan manufacturer" in e.message for e in errs), [e.message for e in errs]


def test_well_known_manufacturer_accepted_without_board(tmp_path):
    """``well_known: true`` grandfathers a manufacturer with no boards."""
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()
    _write_mfr(
        tmp_path / "manufacturers" / "sipeed.yaml",
        slug="sipeed", canonical_name="Sipeed", well_known=True,
    )
    errs = validate_manufacturers(tmp_path)
    assert not [e for e in errs if "orphan" in e.message]


def test_manufacturer_with_board_by_name_match_accepted(tmp_path):
    """A board whose ``manufacturer:`` matches canonical_name satisfies the rule."""
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()
    _write_mfr(
        tmp_path / "manufacturers" / "particle-industries.yaml",
        slug="particle-industries", canonical_name="Particle Industries",
        aliases=["Particle"],
    )
    _write_board(tmp_path / "boards" / "particle" / "boron.ubds.yaml",
                 "boron", "Particle Industries")
    errs = validate_manufacturers(tmp_path)
    assert not [e for e in errs if "orphan" in e.message]


def test_manufacturer_with_board_by_alias_match_accepted(tmp_path):
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()
    _write_mfr(
        tmp_path / "manufacturers" / "particle-industries.yaml",
        slug="particle-industries", canonical_name="Particle Industries",
        aliases=["Particle"],
    )
    # Board uses the alias name, not canonical.
    _write_board(tmp_path / "boards" / "p" / "boron.ubds.yaml",
                 "boron", "Particle")
    errs = validate_manufacturers(tmp_path)
    assert not [e for e in errs if "orphan" in e.message]


def test_manufacturer_with_board_by_manufacturer_slug_match_accepted(tmp_path):
    (tmp_path / "boards").mkdir()
    (tmp_path / "manufacturers").mkdir()
    _write_mfr(
        tmp_path / "manufacturers" / "espressif.yaml",
        slug="espressif", canonical_name="Espressif Systems",
    )
    # Board has manufacturer_slug field.
    p = tmp_path / "boards" / "espressif" / "esp32.ubds.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        'ubds_version: "1.2"\n'
        'name: "esp32"\n'
        'slug: "esp32"\n'
        'manufacturer: "Espressif Systems"\n'
        'manufacturer_slug: "espressif"\n'
        "board_type:\n"
        "  - MCU\n"
        "meta:\n"
        "  sources:\n"
        '    - "https://example.com/d"\n'
        '  product_url: "https://example.com/b"\n',
        encoding="utf-8",
    )
    errs = validate_manufacturers(tmp_path)
    assert not [e for e in errs if "orphan" in e.message]


# ---------------------------------------------------------------------------
# Schema violations surface as ManufacturerError
# ---------------------------------------------------------------------------

def test_missing_homepage_url_rejected(tmp_path):
    (tmp_path / "manufacturers").mkdir()
    p = tmp_path / "manufacturers" / "x.yaml"
    p.write_text(
        'slug: "x"\n'
        'canonical_name: "X"\n'
        'well_known: true\n',
        encoding="utf-8",
    )
    errs = validate_manufacturers(tmp_path)
    assert any("homepage_url" in e.message for e in errs), [e.message for e in errs]


def test_unparseable_yaml_rejected(tmp_path):
    (tmp_path / "manufacturers").mkdir()
    (tmp_path / "manufacturers" / "broken.yaml").write_text(
        "not: valid: yaml: [\n", encoding="utf-8",
    )
    errs = validate_manufacturers(tmp_path)
    assert any("not a valid YAML mapping" in e.message for e in errs), [e.message for e in errs]


def test_no_manufacturers_dir_returns_empty(tmp_path):
    """Tree without manufacturers/ → graceful empty result, not crash."""
    assert validate_manufacturers(tmp_path) == []
