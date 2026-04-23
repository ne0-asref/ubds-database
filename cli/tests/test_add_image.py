"""Tests for ``dbf.images.add_image`` and the ``dbf add-image`` CLI wire-up.

Covers the 18 unit + 4 integration cases from
``artifacts/test-matrix.md §C21.3`` plus a smoke test for the Click surface.

The ``make_png`` helper here is local to this test file. When C21.2's
conftest lands (which owns the shared helper), this copy becomes redundant
and can be removed; see ``artifacts/build/C21.3/test-spec.md`` §"Repo-factory
helper" for the coordination note.
"""
from __future__ import annotations

import struct
import subprocess
import textwrap
from pathlib import Path

import pytest

from dbf.constants import PNG_SIGNATURE


# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def make_png():
    """Factory that writes a byte-unique PNG-signatured file.

    Our code only inspects the 8-byte signature + file size. We encode
    ``width/height/color_type`` into a fake IHDR payload so callers that
    vary those parameters get byte-distinct files (e.g. for overwrite
    assertions). ``pad_bytes`` appends filler — used for oversize
    rejection.
    """
    def _make(
        path: Path,
        *,
        width: int = 16,
        height: int = 16,
        color_type: int = 6,
        pad_bytes: int = 0,
    ) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = bytes(PNG_SIGNATURE)
        # Fake IHDR-like payload. Not a valid PNG chunk — just stable-and-unique bytes.
        payload += struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
        payload += b"\x00" * 32
        if pad_bytes:
            payload += b"\x00" * pad_bytes
        path.write_bytes(payload)

    return _make


@pytest.fixture
def fake_repo(tmp_path, make_png):
    """Create a minimal ubds-database-shaped repo at tmp_path."""
    (tmp_path / "boards").mkdir()
    (tmp_path / "images").mkdir()
    # Schema-compliant per cli/src/dbf/data/ubds-v1.schema.json:
    # board_type is an array; meta.sources is non-empty;
    # data_completeness ∈ {stub,partial,complete}; confidence is an object.
    (tmp_path / "boards" / "rp2040-pico.ubds.yaml").write_text(
        textwrap.dedent(
            """\
            ubds_version: "1.1"
            name: "Raspberry Pi Pico"
            slug: "rp2040-pico"
            manufacturer: "Raspberry Pi"
            board_type:
              - MCU
            # editorial note about this board
            meta:
              sources:
                - "https://www.raspberrypi.com/products/raspberry-pi-pico/"
              product_url: "https://www.raspberrypi.com/products/raspberry-pi-pico/"
              last_verified: "2026-04-01"
              data_completeness: partial
              confidence:
                overall: high
              image_url: null
              pinout_image_url: null
            """
        )
    )
    return tmp_path


@pytest.fixture
def source_png(tmp_path, make_png):
    path = tmp_path / "src_top.png"
    make_png(path, color_type=6)
    return path


# ---------------------------------------------------------------------------
# Tier 1 — unit (18 cases)
# ---------------------------------------------------------------------------

def test_happy_path(fake_repo, source_png):
    from dbf.images import add_image

    result = add_image(
        slug="rp2040-pico",
        source_path=source_png,
        as_view="top-view",
        repo_root=fake_repo,
    )
    assert (fake_repo / "images" / "rp2040-pico" / "top-view.png").exists()
    text = (fake_repo / "boards" / "rp2040-pico.ubds.yaml").read_text()
    expected_url = (
        "https://raw.githubusercontent.com/ne0-asref/ubds-database/main/"
        "images/rp2040-pico/top-view.png"
    )
    assert expected_url in text
    assert result.yaml_edit is not None
    assert result.yaml_edit.line_number >= 1
    assert result.dest.name == "top-view.png"


def test_unknown_slug_with_nearest_match(fake_repo, source_png):
    from dbf.images import add_image, AddImageError

    with pytest.raises(AddImageError) as exc:
        add_image(
            slug="rp2040-picko",
            source_path=source_png,
            as_view="top-view",
            repo_root=fake_repo,
        )
    assert "rp2040-pico" in str(exc.value)


def test_invalid_view(fake_repo, source_png):
    from dbf.images import add_image, AddImageError

    with pytest.raises(AddImageError) as exc:
        add_image(
            slug="rp2040-pico",
            source_path=source_png,
            as_view="sideways",
            repo_root=fake_repo,
        )
    msg = str(exc.value)
    assert "top-view" in msg and "pinout" in msg


def test_source_missing(fake_repo, tmp_path):
    from dbf.images import add_image, AddImageError

    with pytest.raises(AddImageError) as exc:
        add_image(
            slug="rp2040-pico",
            source_path=tmp_path / "nope.png",
            as_view="top-view",
            repo_root=fake_repo,
        )
    assert "not found" in str(exc.value).lower() or "missing" in str(exc.value).lower()


def test_source_not_png(fake_repo, tmp_path):
    from dbf.images import add_image, AddImageError

    (tmp_path / "cat.jpg").write_bytes(b"\xff\xd8\xff")
    with pytest.raises(AddImageError) as exc:
        add_image(
            slug="rp2040-pico",
            source_path=tmp_path / "cat.jpg",
            as_view="top-view",
            repo_root=fake_repo,
        )
    assert "PNG" in str(exc.value)


def test_source_oversize(fake_repo, tmp_path, make_png):
    from dbf.images import add_image, AddImageError

    path = tmp_path / "huge.png"
    make_png(path, pad_bytes=1_100_000)
    with pytest.raises(AddImageError) as exc:
        add_image(
            slug="rp2040-pico",
            source_path=path,
            as_view="top-view",
            repo_root=fake_repo,
        )
    msg = str(exc.value)
    assert "1048576" in msg or "1 MB" in msg or "size" in msg.lower()


def test_dest_exists_no_overwrite(fake_repo, source_png, make_png):
    dest = fake_repo / "images" / "rp2040-pico" / "top-view.png"
    dest.parent.mkdir(parents=True)
    make_png(dest)
    from dbf.images import add_image, AddImageError

    with pytest.raises(AddImageError) as exc:
        add_image(
            slug="rp2040-pico",
            source_path=source_png,
            as_view="top-view",
            repo_root=fake_repo,
        )
    assert "--overwrite" in str(exc.value)


def test_dest_exists_with_overwrite(fake_repo, source_png, make_png, tmp_path):
    dest = fake_repo / "images" / "rp2040-pico" / "top-view.png"
    dest.parent.mkdir(parents=True)
    make_png(dest, width=16)
    original_bytes = dest.read_bytes()
    new_source = tmp_path / "new_src.png"
    make_png(new_source, width=8)  # distinct width → distinct bytes
    from dbf.images import add_image

    result = add_image(
        slug="rp2040-pico",
        source_path=new_source,
        as_view="top-view",
        repo_root=fake_repo,
        overwrite=True,
    )
    assert dest.read_bytes() != original_bytes
    assert result.backup is not None


def test_no_write_yaml(fake_repo, source_png):
    yaml_before = (fake_repo / "boards" / "rp2040-pico.ubds.yaml").read_text()
    from dbf.images import add_image

    result = add_image(
        slug="rp2040-pico",
        source_path=source_png,
        as_view="top-view",
        repo_root=fake_repo,
        write_yaml=False,
    )
    assert (fake_repo / "images" / "rp2040-pico" / "top-view.png").exists()
    yaml_after = (fake_repo / "boards" / "rp2040-pico.ubds.yaml").read_text()
    assert yaml_before == yaml_after
    assert result.yaml_edit is None
    assert result.backup is None


def test_as_top_view_writes_image_url(fake_repo, source_png):
    from dbf.images import add_image

    add_image(
        slug="rp2040-pico",
        source_path=source_png,
        as_view="top-view",
        repo_root=fake_repo,
    )
    text = (fake_repo / "boards" / "rp2040-pico.ubds.yaml").read_text()
    assert "main/images/rp2040-pico/top-view.png" in text


def test_as_pinout_writes_pinout_url(fake_repo, source_png):
    from dbf.images import add_image

    add_image(
        slug="rp2040-pico",
        source_path=source_png,
        as_view="pinout",
        repo_root=fake_repo,
    )
    text = (fake_repo / "boards" / "rp2040-pico.ubds.yaml").read_text()
    assert "main/images/rp2040-pico/pinout.png" in text
    assert "pinout_image_url:" in text


def test_as_angle_writes_image_url_with_angle_stem(fake_repo, source_png):
    from dbf.images import add_image

    add_image(
        slug="rp2040-pico",
        source_path=source_png,
        as_view="angle",
        repo_root=fake_repo,
    )
    text = (fake_repo / "boards" / "rp2040-pico.ubds.yaml").read_text()
    assert "main/images/rp2040-pico/angle.png" in text


def test_missing_meta_block(fake_repo, source_png):
    (fake_repo / "boards" / "rp2040-pico.ubds.yaml").write_text(
        'slug: "rp2040-pico"\nname: "Pico"\n'
    )
    from dbf.images import add_image, AddImageError

    with pytest.raises(AddImageError) as exc:
        add_image(
            slug="rp2040-pico",
            source_path=source_png,
            as_view="top-view",
            repo_root=fake_repo,
        )
    assert "meta" in str(exc.value).lower()
    # Fail-fast: image must NOT have been copied because pre-write YAML check runs first.
    assert not (fake_repo / "images" / "rp2040-pico" / "top-view.png").exists()


def test_comments_preserved(fake_repo, source_png):
    yaml_before = (fake_repo / "boards" / "rp2040-pico.ubds.yaml").read_text()
    assert "# editorial note about this board" in yaml_before
    from dbf.images import add_image

    add_image(
        slug="rp2040-pico",
        source_path=source_png,
        as_view="top-view",
        repo_root=fake_repo,
    )
    yaml_after = (fake_repo / "boards" / "rp2040-pico.ubds.yaml").read_text()
    assert "# editorial note about this board" in yaml_after


def test_key_order_preserved(fake_repo, source_png):
    from dbf.images import add_image

    yaml_before = (fake_repo / "boards" / "rp2040-pico.ubds.yaml").read_text().splitlines()
    sources_before = next(
        i for i, l in enumerate(yaml_before) if l.strip().startswith("sources:")
    )
    last_verified_before = next(
        i for i, l in enumerate(yaml_before) if l.strip().startswith("last_verified:")
    )
    assert sources_before < last_verified_before

    add_image(
        slug="rp2040-pico",
        source_path=source_png,
        as_view="top-view",
        repo_root=fake_repo,
    )
    yaml_after = (fake_repo / "boards" / "rp2040-pico.ubds.yaml").read_text().splitlines()
    sources_after = next(
        i for i, l in enumerate(yaml_after) if l.strip().startswith("sources:")
    )
    last_verified_after = next(
        i for i, l in enumerate(yaml_after) if l.strip().startswith("last_verified:")
    )
    assert sources_after < last_verified_after


def test_pre_write_validation_abort(fake_repo, source_png):
    """Corrupt the board YAML so the post-edit text fails schema validation.

    The test asserts only that ``AddImageError`` is raised — the exact
    failure path (editor refusing flow-style meta, or validator flagging
    missing required fields) is implementation detail.
    """
    (fake_repo / "boards" / "rp2040-pico.ubds.yaml").write_text(
        'slug: "rp2040-pico"\nmeta: {}\n'
    )
    from dbf.images import add_image, AddImageError

    with pytest.raises(AddImageError):
        add_image(
            slug="rp2040-pico",
            source_path=source_png,
            as_view="top-view",
            repo_root=fake_repo,
        )


def test_atomic_write_no_tmp_visible(fake_repo, source_png):
    from dbf.images import add_image

    add_image(
        slug="rp2040-pico",
        source_path=source_png,
        as_view="top-view",
        repo_root=fake_repo,
    )
    tmps = list((fake_repo / "images" / "rp2040-pico").glob("*.tmp"))
    assert not tmps, f"tmp files left behind: {tmps}"
    yaml_tmps = list((fake_repo / "boards").glob("*.tmp"))
    assert not yaml_tmps, f"yaml tmp files left behind: {yaml_tmps}"


def test_uppercase_slug_rejected(fake_repo, source_png):
    from dbf.images import add_image, AddImageError

    with pytest.raises(AddImageError) as exc:
        add_image(
            slug="RP2040-Pico",
            source_path=source_png,
            as_view="top-view",
            repo_root=fake_repo,
        )
    assert "lowercase" in str(exc.value).lower()
    assert not (fake_repo / "images" / "RP2040-Pico").exists()
    assert not (fake_repo / "images" / "rp2040-pico").exists()


def test_slug_path_traversal_rejected(fake_repo, source_png, tmp_path):
    """Security guard: a slug with '..' or '/' must be rejected before any
    path is joined under ``repo_root``. Otherwise an attacker-controlled
    slug could escape the repo boundary and plant files elsewhere on disk.
    """
    from dbf.images import add_image, AddImageError

    for bad in ("../evil", "foo/bar", "a.b", "foo\\bar"):
        with pytest.raises(AddImageError) as exc:
            add_image(
                slug=bad,
                source_path=source_png,
                as_view="top-view",
                repo_root=fake_repo,
            )
        msg = str(exc.value).lower()
        assert "lowercase" in msg or "invalid slug" in msg, (
            f"expected format-rejection for slug {bad!r}, got: {exc.value}"
        )
    # Ensure nothing leaked onto disk outside the expected dirs.
    assert not any(tmp_path.glob("**/evil"))


# ---------------------------------------------------------------------------
# Tier 2 — integration (4 cases)
# ---------------------------------------------------------------------------

def test_add_image_then_validate(fake_repo, source_png):
    from dbf.images import add_image
    from dbf.validate import validate_file

    add_image(
        slug="rp2040-pico",
        source_path=source_png,
        as_view="top-view",
        repo_root=fake_repo,
    )
    result = validate_file(fake_repo / "boards" / "rp2040-pico.ubds.yaml")
    assert not result.errors, f"validate_file errors: {result.errors}"
    assert result.parse_error is None


def test_two_views_same_slug(fake_repo, source_png, tmp_path, make_png):
    from dbf.images import add_image

    pinout_src = tmp_path / "pinout.png"
    make_png(pinout_src)
    add_image(
        slug="rp2040-pico",
        source_path=source_png,
        as_view="top-view",
        repo_root=fake_repo,
    )
    add_image(
        slug="rp2040-pico",
        source_path=pinout_src,
        as_view="pinout",
        repo_root=fake_repo,
    )
    assert (fake_repo / "images" / "rp2040-pico" / "top-view.png").exists()
    assert (fake_repo / "images" / "rp2040-pico" / "pinout.png").exists()
    text = (fake_repo / "boards" / "rp2040-pico.ubds.yaml").read_text()
    assert "main/images/rp2040-pico/top-view.png" in text
    assert "main/images/rp2040-pico/pinout.png" in text


def test_fallback_then_top_view(fake_repo, source_png, tmp_path, make_png):
    from dbf.images import add_image

    angle_src = tmp_path / "angle.png"
    make_png(angle_src)
    add_image(
        slug="rp2040-pico",
        source_path=angle_src,
        as_view="angle",
        repo_root=fake_repo,
    )
    text_mid = (fake_repo / "boards" / "rp2040-pico.ubds.yaml").read_text()
    assert "angle.png" in text_mid

    add_image(
        slug="rp2040-pico",
        source_path=source_png,
        as_view="top-view",
        repo_root=fake_repo,
    )
    text_end = (fake_repo / "boards" / "rp2040-pico.ubds.yaml").read_text()
    assert "top-view.png" in text_end
    assert "angle.png" not in text_end


def test_git_status_surface(fake_repo, source_png):
    env = {
        **dict(__import__("os").environ),
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@test",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@test",
    }
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=fake_repo, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=fake_repo, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial"], cwd=fake_repo, check=True, env=env
    )
    from dbf.images import add_image

    add_image(
        slug="rp2040-pico",
        source_path=source_png,
        as_view="top-view",
        repo_root=fake_repo,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=fake_repo,
        capture_output=True,
        text=True,
        env=env,
    ).stdout
    assert "images/rp2040-pico/top-view.png" in status
    assert "boards/rp2040-pico.ubds.yaml" in status


# ---------------------------------------------------------------------------
# CLI surface smoke — Click subcommand is wired and delegates to add_image.
# ---------------------------------------------------------------------------

def test_cli_add_image_happy_path(runner, fake_repo, source_png, monkeypatch):
    from dbf.cli import main

    monkeypatch.setenv("DBF_REPO_ROOT", str(fake_repo))
    result = runner.invoke(
        main,
        ["add-image", "rp2040-pico", str(source_png), "--as", "top-view"],
    )
    assert result.exit_code == 0, result.output
    assert (fake_repo / "images" / "rp2040-pico" / "top-view.png").exists()
    assert "copied" in result.output
    assert "next: git add" in result.output


def test_cli_add_image_reports_error(runner, fake_repo, source_png, monkeypatch):
    from dbf.cli import main

    monkeypatch.setenv("DBF_REPO_ROOT", str(fake_repo))
    result = runner.invoke(
        main,
        ["add-image", "rp2040-picko", str(source_png), "--as", "top-view"],
    )
    assert result.exit_code == 1
    # `rp2040-pico` should appear in the nearest-match suggestion output.
    combined = result.output + (result.stderr if result.stderr_bytes else "")
    assert "rp2040-pico" in combined


def test_cli_add_image_help_lists_flags(runner):
    from dbf.cli import main

    result = runner.invoke(main, ["add-image", "--help"])
    assert result.exit_code == 0
    for flag in ("--as", "--no-write-yaml", "--overwrite"):
        assert flag in result.output, f"missing flag {flag!r} in add-image --help"
