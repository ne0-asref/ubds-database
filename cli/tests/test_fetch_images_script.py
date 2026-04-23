"""Black-box tests for scripts/fetch-images.sh (C21.5).

Invokes the shell script via subprocess and asserts on its stdout. Integration
tests use a local HTTP server to exercise the real `curl` path without hitting
the network. The script's test-observable contract is the set of output strings
documented in `artifacts/build/C21.5/spec.md`.
"""
from __future__ import annotations

import http.server
import socketserver
import subprocess
import threading
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "fetch-images.sh"


@pytest.fixture
def fake_repo_for_fetch(tmp_path):
    """Minimal repo shape: boards/ + images/ rooted at a tmp_path."""
    (tmp_path / "boards").mkdir()
    (tmp_path / "images").mkdir()
    return tmp_path


def _write_board(repo: Path, slug: str, image_url=None, pinout_url=None) -> None:
    """Emit a tiny .ubds.yaml under repo/boards/ exposing only slug + meta urls."""
    parts = [f'slug: "{slug}"', "meta:"]
    if image_url is not None:
        parts.append(f'  image_url: "{image_url}"' if image_url else "  image_url: null")
    if pinout_url is not None:
        parts.append(
            f'  pinout_image_url: "{pinout_url}"' if pinout_url else "  pinout_image_url: null"
        )
    (repo / "boards" / f"{slug}.ubds.yaml").write_text("\n".join(parts) + "\n")


def _run(repo: Path, *extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *extra_args],
        cwd=repo,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Tier 1 — unit (--dry-run only, no network)
# ---------------------------------------------------------------------------


def test_dryrun_pinout_url(fake_repo_for_fetch):
    """5.1.1 — a non-canonical pinout URL should surface its own WOULD FETCH line."""
    _write_board(fake_repo_for_fetch, "foo", pinout_url="https://example.com/p.png")
    r = _run(fake_repo_for_fetch, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "WOULD FETCH foo pinout" in r.stdout
    assert "images/foo/pinout.png" in r.stdout
