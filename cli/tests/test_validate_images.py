"""C21.2 — `dbf validate --check-images` test suite.

Covers the 13 rules from eng-plan §4 C21.2 plus CLI-flag wiring + a
synthetic fixture-tree integration sweep. Tests mirror the structure of
``artifacts/build/C21.2/test-spec.md``.

Layout
------
- ``test_rule{N}_*`` — per-rule unit tests (Tier 1, 24 cases).
- ``test_flag_*`` — CLI-flag default + override tests (Tier 1, 4 cases).
- ``test_fixture_*`` — Tier 2 integration tests on the synthetic fixture tree.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner


# ---------------------------------------------------------------------------
# Rule 1 — symlinked slug directory rejected.
# ---------------------------------------------------------------------------

def test_rule1_symlink_dir_rejected(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "boards" / "foo-real.ubds.yaml").write_text("slug: foo-real\nmeta: {}\n")
    real = tmp_path / "images" / "foo-real"
    real.mkdir(parents=True)
    make_png(real / "top-view.png")
    (tmp_path / "images" / "foo").symlink_to(real)

    results = check_images(tmp_path)
    assert any(
        r.severity == "error" and "symlink" in r.message.lower()
        for r in results
    ), f"expected symlink rejection, got {[r.message for r in results]}"


# ---------------------------------------------------------------------------
# Rule 2 — mixed-case slug directory.
# ---------------------------------------------------------------------------

def test_rule2_mixed_case_slug(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "images" / "MySlug").mkdir(parents=True)
    make_png(tmp_path / "images" / "MySlug" / "top-view.png")

    results = check_images(tmp_path)
    assert any(
        r.severity == "error" and "lowercase" in r.message.lower()
        for r in results
    )


# ---------------------------------------------------------------------------
# Rule 3 — nested subdirectory under images/<slug>/.
# ---------------------------------------------------------------------------

def test_rule3_nested_subdir(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    nested = tmp_path / "images" / "foo" / "sub"
    nested.mkdir(parents=True)
    make_png(nested / "top-view.png")

    results = check_images(tmp_path)
    assert any(
        r.severity == "error" and "nested" in r.message.lower()
        for r in results
    )


# ---------------------------------------------------------------------------
# Rule 4 — non-.png extension.
# ---------------------------------------------------------------------------

def test_rule4_non_png_extension(tmp_path):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "images" / "foo").mkdir(parents=True)
    (tmp_path / "images" / "foo" / "top-view.jpg").write_bytes(b"JPEG stub")

    results = check_images(tmp_path)
    assert any(
        r.severity == "error" and ".png" in r.message
        for r in results
    )


# ---------------------------------------------------------------------------
# Rule 5 — disallowed filename stem.
# ---------------------------------------------------------------------------

def test_rule5_disallowed_stem(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "images" / "foo").mkdir(parents=True)
    make_png(tmp_path / "images" / "foo" / "pins.png")

    results = check_images(tmp_path)
    assert any(
        r.severity == "error" and "disallowed" in r.message.lower()
        for r in results
    )


# ---------------------------------------------------------------------------
# Rule 6 — PNG signature fail (two sub-cases).
# ---------------------------------------------------------------------------

def test_rule6a_jpeg_bytes_under_png_name(tmp_path):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "images" / "foo").mkdir(parents=True)
    (tmp_path / "images" / "foo" / "top-view.png").write_bytes(b"\xff\xd8\xff" + b"\x00" * 20)

    results = check_images(tmp_path)
    assert any(
        r.severity == "error" and "png" in r.message.lower()
        for r in results
    )


def test_rule6b_truncated_png(tmp_path):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "images" / "foo").mkdir(parents=True)
    (tmp_path / "images" / "foo" / "top-view.png").write_bytes(b"\x89PNG")

    results = check_images(tmp_path)
    assert any(
        r.severity == "error" and "png" in r.message.lower()
        for r in results
    )


# ---------------------------------------------------------------------------
# Rule 7 — oversize (> 1 MiB).
# ---------------------------------------------------------------------------

def test_rule7_oversize(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "images" / "foo").mkdir(parents=True)
    make_png(tmp_path / "images" / "foo" / "top-view.png", pad_bytes=1_100_000)

    results = check_images(tmp_path)
    assert any(
        r.severity == "error" and ("1 MB" in r.message or "size" in r.message.lower())
        for r in results
    )


# ---------------------------------------------------------------------------
# Rule 8 — RGBA warn (3 sub-cases).
# ---------------------------------------------------------------------------

def test_rule8a_rgb_top_view_warns(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "boards" / "foo.ubds.yaml").write_text("slug: foo\nmeta: {}\n")
    (tmp_path / "images" / "foo").mkdir(parents=True)
    make_png(tmp_path / "images" / "foo" / "top-view.png", color_type=2)

    results = check_images(tmp_path)
    assert any(
        r.severity == "warn" and "rgba" in r.message.lower()
        for r in results
    )


def test_rule8b_rgba_top_view_clean(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "boards" / "foo.ubds.yaml").write_text("slug: foo\nmeta: {}\n")
    (tmp_path / "images" / "foo").mkdir(parents=True)
    make_png(tmp_path / "images" / "foo" / "top-view.png", color_type=6)

    results = check_images(tmp_path)
    assert not any(
        r.severity == "warn" and "rgba" in r.message.lower()
        for r in results
    )


def test_rule8c_opaque_pinout_no_warn(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "boards" / "foo.ubds.yaml").write_text("slug: foo\nmeta: {}\n")
    (tmp_path / "images" / "foo").mkdir(parents=True)
    make_png(tmp_path / "images" / "foo" / "pinout.png", color_type=2)

    results = check_images(tmp_path)
    assert not any(
        r.severity == "warn" and "rgba" in r.message.lower()
        for r in results
    )


# ---------------------------------------------------------------------------
# Rule 9 — orphan images/<slug>/ (no matching YAML).
# ---------------------------------------------------------------------------

def test_rule9_orphan(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "images" / "deleted-board").mkdir(parents=True)
    make_png(tmp_path / "images" / "deleted-board" / "top-view.png")

    results = check_images(tmp_path)
    assert any(
        r.severity == "warn" and "orphan" in r.message.lower()
        for r in results
    )


# ---------------------------------------------------------------------------
# Rule 10 — fallback-only preference warning.
# ---------------------------------------------------------------------------

def test_rule10a_fallback_only_warns(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "boards" / "foo.ubds.yaml").write_text("slug: foo\nmeta: {}\n")
    (tmp_path / "images" / "foo").mkdir(parents=True)
    make_png(tmp_path / "images" / "foo" / "block-diagram.png")

    results = check_images(tmp_path)
    errors = [r for r in results if r.severity == "error"]
    warns = [r for r in results if r.severity == "warn" and "top-view" in r.message.lower()]
    assert not errors, f"fallback-only must not error: {[r.message for r in errors]}"
    assert warns, "expected top-view preference warn"


def test_rule10b_top_view_plus_fallback_no_warn(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    yaml_content = (
        "slug: foo\n"
        "meta:\n"
        "  image_url: https://raw.githubusercontent.com/ne0-asref/ubds-database/main/images/foo/top-view.png\n"
    )
    (tmp_path / "boards" / "foo.ubds.yaml").write_text(yaml_content)
    (tmp_path / "images" / "foo").mkdir(parents=True)
    make_png(tmp_path / "images" / "foo" / "top-view.png")
    make_png(tmp_path / "images" / "foo" / "angle.png")

    results = check_images(tmp_path)
    assert not any(
        r.severity == "warn" and "top-view" in r.message.lower()
        for r in results
    )


# ---------------------------------------------------------------------------
# Rule 11 — URL coupling (5 sub-cases).
# ---------------------------------------------------------------------------

def test_rule11a_non_canonical_url_errors(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "boards" / "foo.ubds.yaml").write_text(
        "slug: foo\nmeta:\n  image_url: https://example.com/foo.png\n"
    )
    (tmp_path / "images" / "foo").mkdir(parents=True)
    make_png(tmp_path / "images" / "foo" / "top-view.png")

    results = check_images(tmp_path)
    assert any(
        r.severity == "error" and "image_url" in r.message
        for r in results
    )


def test_rule11b_null_url_with_file_errors(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "boards" / "foo.ubds.yaml").write_text(
        "slug: foo\nmeta:\n  image_url: null\n"
    )
    (tmp_path / "images" / "foo").mkdir(parents=True)
    make_png(tmp_path / "images" / "foo" / "top-view.png")

    results = check_images(tmp_path)
    assert any(
        r.severity == "error" and "image_url" in r.message
        for r in results
    )


def test_rule11c_pinout_coupling(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "boards" / "foo.ubds.yaml").write_text(
        "slug: foo\nmeta:\n  pinout_image_url: https://example.com/p.png\n"
    )
    (tmp_path / "images" / "foo").mkdir(parents=True)
    make_png(tmp_path / "images" / "foo" / "pinout.png")

    results = check_images(tmp_path)
    assert any(
        r.severity == "error" and "pinout_image_url" in r.message
        for r in results
    )


def test_rule11d_canonical_url_ok(tmp_path, make_png):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "boards" / "foo.ubds.yaml").write_text(
        "slug: foo\nmeta:\n  image_url: https://raw.githubusercontent.com/ne0-asref/ubds-database/main/images/foo/top-view.png\n"
    )
    (tmp_path / "images" / "foo").mkdir(parents=True)
    make_png(tmp_path / "images" / "foo" / "top-view.png")

    results = check_images(tmp_path)
    assert not any(
        r.severity == "error" and "image_url" in r.message
        for r in results
    )


def test_rule11e_no_file_free_url_ok(tmp_path):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "boards" / "foo.ubds.yaml").write_text(
        "slug: foo\nmeta:\n  image_url: https://example.com/manufacturer-kit.png\n"
    )
    (tmp_path / "images").mkdir()

    results = check_images(tmp_path)
    assert not any(
        r.severity == "error" and "image_url" in r.message
        for r in results
    )


# ---------------------------------------------------------------------------
# Rule 12 — empty slug directory is silently ignored.
# ---------------------------------------------------------------------------

def test_rule12_empty_dir_silent(tmp_path):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "boards" / "foo.ubds.yaml").write_text("slug: foo\nmeta: {}\n")
    (tmp_path / "images" / "foo").mkdir(parents=True)

    results = check_images(tmp_path)
    assert not any(r.severity == "error" for r in results), (
        f"empty images/foo/ must be silent, got {[r.message for r in results]}"
    )


# ---------------------------------------------------------------------------
# Rule 13 — cross-file slug uniqueness + filename coupling (4 sub-cases).
# ---------------------------------------------------------------------------

def test_rule13a_duplicate_slug_errors(tmp_path):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "boards" / "arduino-uno.ubds.yaml").write_text("slug: duplicated\nmeta: {}\n")
    (tmp_path / "boards" / "arduino-uno-r3.ubds.yaml").write_text("slug: duplicated\nmeta: {}\n")
    (tmp_path / "images").mkdir()

    results = check_images(tmp_path)
    dup_errs = [
        r for r in results
        if r.severity == "error" and "duplicated" in r.message and "duplicate" in r.message.lower()
    ]
    assert dup_errs, f"expected duplicate-slug error, got {[r.message for r in results]}"
    assert "arduino-uno.ubds.yaml" in dup_errs[0].message
    assert "arduino-uno-r3.ubds.yaml" in dup_errs[0].message


def test_rule13b_slug_mismatches_filename(tmp_path):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    (tmp_path / "boards" / "arduino-uno.ubds.yaml").write_text("slug: arduino-r3\nmeta: {}\n")
    (tmp_path / "images").mkdir()

    results = check_images(tmp_path)
    assert any(
        r.severity == "error" and "arduino-uno" in r.message and "arduino-r3" in r.message
        for r in results
    )


def test_rule13c_triple_collision_single_error(tmp_path):
    from dbf.validate import check_images

    (tmp_path / "boards").mkdir()
    for n in ["collide-a", "collide-b", "collide-c"]:
        # pick filenames that embed the slug so Rule 13b doesn't fire
        (tmp_path / "boards" / f"{n}.ubds.yaml").write_text("slug: collide-a\nmeta: {}\n")
    (tmp_path / "images").mkdir()

    results = check_images(tmp_path)
    dup_errs = [
        r for r in results
        if r.severity == "error" and "duplicate" in r.message.lower() and "collide-a" in r.message
    ]
    assert len(dup_errs) == 1, (
        f"expected single consolidated duplicate-slug error, got {len(dup_errs)}: "
        f"{[r.message for r in dup_errs]}"
    )


def test_rule13d_real_repo_regression():
    from dbf.validate import check_images

    live = Path("/home/omar/ubds-database")
    if not live.exists():
        pytest.skip("live repo not available")
    results = check_images(live)
    slug_errs = [
        r for r in results
        if r.severity == "error" and "duplicate" in r.message.lower()
    ]
    assert not slug_errs, (
        f"live repo has slug uniqueness issues: {[r.message for r in slug_errs]}"
    )


# ---------------------------------------------------------------------------
# Tier 1 — CLI-flag tests (4).
# ---------------------------------------------------------------------------

def _invoke(args):
    from dbf.cli import main
    return CliRunner().invoke(main, args)


def _seed_red_image_tree(root: Path) -> None:
    """Create a tree with a Rule-5 image error so image-check presence is observable."""
    (root / "boards").mkdir()
    (root / "boards" / "foo.ubds.yaml").write_text("slug: foo\nmeta: {}\n")
    (root / "images" / "foo").mkdir(parents=True)
    (root / "images" / "foo" / "pins.png").write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
    )


def test_flag_F1_default_on_for_dir(tmp_path):
    """Directory arg default should run check_images (Rule 5 error surfaces)."""
    _seed_red_image_tree(tmp_path)
    result = _invoke(["validate", str(tmp_path / "boards")])
    assert "pins.png" in result.output or "disallowed" in result.output.lower(), (
        f"image check should have run; output:\n{result.output}"
    )


def test_flag_F2_default_off_for_file(tmp_path):
    """Single-file arg default should skip check_images (image error absent)."""
    _seed_red_image_tree(tmp_path)
    result = _invoke(["validate", str(tmp_path / "boards" / "foo.ubds.yaml")])
    assert "pins.png" not in result.output and "IMAGE" not in result.output, (
        f"image check should NOT have run by default on a single file:\n{result.output}"
    )


def test_flag_F3_explicit_check_on_file(tmp_path):
    """`--check-images` on a single-file invocation should run the check."""
    _seed_red_image_tree(tmp_path)
    result = _invoke([
        "validate",
        str(tmp_path / "boards" / "foo.ubds.yaml"),
        "--check-images",
    ])
    assert "pins.png" in result.output or "disallowed" in result.output.lower(), (
        f"--check-images on file should run the check:\n{result.output}"
    )


def test_flag_F4_explicit_no_check_on_dir(tmp_path):
    """`--no-check-images` on a directory should skip the check."""
    _seed_red_image_tree(tmp_path)
    result = _invoke([
        "validate",
        str(tmp_path / "boards"),
        "--no-check-images",
    ])
    assert "pins.png" not in result.output and "IMAGE" not in result.output, (
        f"--no-check-images on dir should skip the check:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# Tier 2 — fixture tree integration.
# ---------------------------------------------------------------------------

FIXTURE = Path(__file__).parent / "fixtures" / "c21-images"


def test_fixture_whole_tree_counts(make_fixture_pngs):
    from dbf.validate import check_images

    results = check_images(FIXTURE)
    errors = [r for r in results if r.severity == "error"]
    warns = [r for r in results if r.severity == "warn"]
    assert len(errors) == 5, (
        f"expected 5 errors (3 image + 2 slug), got {len(errors)}: "
        f"{[r.message for r in errors]}"
    )
    assert len(warns) == 2, (
        f"expected 2 warns (orphan + fallback-only), got {len(warns)}: "
        f"{[r.message for r in warns]}"
    )


def test_fixture_clean_single_file_no_image_check(make_fixture_pngs):
    result = _invoke([
        "validate",
        str(FIXTURE / "boards" / "clean-board.ubds.yaml"),
    ])
    assert result.exit_code == 0, (
        f"clean-board single-file must exit 0, got {result.exit_code}:\n{result.output}"
    )


def test_fixture_error_warn_messages(make_fixture_pngs):
    from dbf.validate import check_images

    results = check_images(FIXTURE)
    err_msgs = [r.message for r in results if r.severity == "error"]
    warn_msgs = [r.message for r in results if r.severity == "warn"]
    assert any("pins.png" in m for m in err_msgs), err_msgs  # Rule 5
    assert any("1 MB" in m or "size" in m.lower() for m in err_msgs), err_msgs  # Rule 7
    assert any("image_url" in m for m in err_msgs), err_msgs  # Rule 11
    assert any("duplicated" in m for m in err_msgs), err_msgs  # Rule 13a
    assert any("something-else" in m for m in err_msgs), err_msgs  # Rule 13b
    assert any("orphan" in m.lower() for m in warn_msgs), warn_msgs  # Rule 9
    assert any("top-view" in m.lower() for m in warn_msgs), warn_msgs  # Rule 10


def test_fixture_real_repo_clean(make_fixture_pngs):
    from dbf.validate import check_images

    live = Path("/home/omar/ubds-database")
    if not live.exists():
        pytest.skip("live repo not available")
    results = check_images(live)
    errors = [r for r in results if r.severity == "error"]
    assert not errors, (
        f"live repo unexpectedly errors: {[r.message for r in errors]}"
    )
