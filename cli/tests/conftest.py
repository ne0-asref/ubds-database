"""Shared pytest fixtures for the dbf test suite."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Callable

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_cache_dir(tmp_path, monkeypatch):
    """Every test gets its own DBF_CACHE_DIR so nothing pollutes ~/.devboardfinder/."""
    cache_dir = tmp_path / "dbf-cache"
    cache_dir.mkdir()
    monkeypatch.setenv("DBF_CACHE_DIR", str(cache_dir))


# ---------------------------------------------------------------------------
# PNG generator — stdlib-only, used by C21.2 image validation tests.
# ---------------------------------------------------------------------------

def _chunk(name: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)
    return length + name + data + crc


def _make_png(
    dest: Path,
    color_type: int = 6,
    width: int = 4,
    height: int = 4,
    pad_bytes: int = 0,
) -> None:
    """Write a minimal valid PNG at ``dest``.

    ``color_type`` follows the IHDR convention (6 = RGBA, 2 = RGB, 0 = greyscale).
    ``pad_bytes`` appends raw bytes after IEND so callers can produce oversize
    fixtures without shipping large binaries in the repo.
    """
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    ihdr_chunk = _chunk(b"IHDR", ihdr_data)
    bytes_per_pixel = 4 if color_type == 6 else 3 if color_type == 2 else 1
    raw = b"".join(b"\x00" + b"\x00" * (width * bytes_per_pixel) for _ in range(height))
    idat = _chunk(b"IDAT", zlib.compress(raw))
    iend = _chunk(b"IEND", b"")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(sig + ihdr_chunk + idat + iend + b"\x00" * pad_bytes)


@pytest.fixture
def make_png() -> Callable[..., None]:
    """Expose ``_make_png`` as a pytest fixture for per-rule unit tests."""
    return _make_png


# ---------------------------------------------------------------------------
# C21.2 Tier 2 fixture tree — write PNGs on demand into cli/tests/fixtures/c21-images.
# ---------------------------------------------------------------------------

C21_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "c21-images"


@pytest.fixture
def make_fixture_pngs() -> Path:
    """Populate ``cli/tests/fixtures/c21-images/images/`` with the 6 generated PNGs.

    PNGs are regenerated every test invocation so the checked-in tree stays
    binary-free. Returns the fixture root path for convenience.
    """
    images = C21_FIXTURE_ROOT / "images"
    # clean-board — RGBA top-view (canonical green path)
    _make_png(images / "clean-board" / "top-view.png", color_type=6)
    # fallback-only — RGBA block-diagram (no top-view)
    _make_png(images / "fallback-only" / "block-diagram.png", color_type=6)
    # orphan (no matching YAML)
    _make_png(images / "deleted-board" / "top-view.png", color_type=6)
    # disallowed filename stem — still byte-valid PNG so rule 5 fires, not rule 6
    _make_png(images / "red-disallowed" / "pins.png", color_type=6)
    # oversize — padded to exceed 1 MiB
    _make_png(images / "red-oversize" / "top-view.png", color_type=6, pad_bytes=1_100_000)
    # URL-mismatch — valid PNG paired with a non-canonical meta.image_url
    _make_png(images / "red-url-mismatch" / "top-view.png", color_type=6)
    return C21_FIXTURE_ROOT
