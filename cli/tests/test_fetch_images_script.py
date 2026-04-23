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


def test_dryrun_both_urls(fake_repo_for_fetch):
    """5.1.2 — when both URLs are present, both fetches surface independently."""
    _write_board(
        fake_repo_for_fetch,
        "foo",
        image_url="https://example.com/t.png",
        pinout_url="https://example.com/p.png",
    )
    r = _run(fake_repo_for_fetch, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "WOULD FETCH foo top-view" in r.stdout
    assert "WOULD FETCH foo pinout" in r.stdout


def test_skip_canonical(fake_repo_for_fetch):
    """5.1.3 — an already-canonical URL is skipped, not re-fetched."""
    canon_top = (
        "https://raw.githubusercontent.com/ne0-asref/ubds-database/"
        "main/images/foo/top-view.png"
    )
    _write_board(fake_repo_for_fetch, "foo", image_url=canon_top)
    r = _run(fake_repo_for_fetch, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "SKIP foo top-view: already canonical" in r.stdout
    assert "WOULD FETCH foo top-view" not in r.stdout


def test_skip_cached(fake_repo_for_fetch):
    """5.1.4 — a cached file on disk shortcuts the fetch even on --dry-run."""
    _write_board(fake_repo_for_fetch, "foo", image_url="https://example.com/t.png")
    (fake_repo_for_fetch / "images" / "foo").mkdir()
    (fake_repo_for_fetch / "images" / "foo" / "top-view.png").write_bytes(
        b"\x89PNG\r\n\x1a\n"
    )
    r = _run(fake_repo_for_fetch, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "SKIP foo top-view: already cached" in r.stdout


def test_slug_filter(fake_repo_for_fetch):
    """5.1.5 — --slug narrows the loop to a single board."""
    _write_board(fake_repo_for_fetch, "foo", image_url="https://example.com/foo.png")
    _write_board(fake_repo_for_fetch, "bar", image_url="https://example.com/bar.png")
    r = _run(fake_repo_for_fetch, "--dry-run", "--slug", "foo")
    assert r.returncode == 0, r.stderr
    assert "WOULD FETCH foo top-view" in r.stdout
    assert "WOULD FETCH bar" not in r.stdout


# ---------------------------------------------------------------------------
# Tier 2 — integration (loopback HTTP, exercises real curl)
# ---------------------------------------------------------------------------


_PNG_STUB = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


class _Handler(http.server.BaseHTTPRequestHandler):
    """Canned responses for the fetch-images.sh integration tests."""

    _responses = {
        "/top.png": (200, _PNG_STUB),
        "/pinout.png": (200, _PNG_STUB),
        "/404.png": (404, b""),
    }

    def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler API.
        code, body = self._responses.get(self.path, (404, b""))
        self.send_response(code)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args, **_kwargs):  # silence per-request access logs.
        pass


@pytest.fixture
def mock_http_server():
    """Spin a tiny HTTPServer on 127.0.0.1:<random> and yield the bound port."""
    srv = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


def test_fetch_both_from_mock(fake_repo_for_fetch, mock_http_server):
    """5.2.1 — both URLs served: both files land at the canonical paths."""
    port = mock_http_server
    _write_board(
        fake_repo_for_fetch,
        "foo",
        image_url=f"http://127.0.0.1:{port}/top.png",
        pinout_url=f"http://127.0.0.1:{port}/pinout.png",
    )
    r = _run(fake_repo_for_fetch)
    assert r.returncode == 0, r.stderr
    assert (fake_repo_for_fetch / "images" / "foo" / "top-view.png").exists()
    assert (fake_repo_for_fetch / "images" / "foo" / "pinout.png").exists()
    assert "OK" in r.stdout


def test_fetch_pinout_404_continues(fake_repo_for_fetch, mock_http_server):
    """5.2.2 — pinout 404 is logged as FAIL, top-view still saved, exit 0."""
    port = mock_http_server
    _write_board(
        fake_repo_for_fetch,
        "foo",
        image_url=f"http://127.0.0.1:{port}/top.png",
        pinout_url=f"http://127.0.0.1:{port}/404.png",
    )
    r = _run(fake_repo_for_fetch)
    assert r.returncode == 0, r.stderr
    assert (fake_repo_for_fetch / "images" / "foo" / "top-view.png").exists()
    assert not (fake_repo_for_fetch / "images" / "foo" / "pinout.png").exists()
    assert "FAIL" in r.stdout
