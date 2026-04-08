"""Board data sourcing + local cache.

Auto-fetch on first run pulls every `boards/*.ubds.yaml` from
ne0-asref/ubds-database via the GitHub git-tree API + raw.githubusercontent.com.

Cache lives at `~/.devboardfinder/boards/` (override via DBF_CACHE_DIR).
Tests can short-circuit the cache entirely with DBF_BOARDS_DIR.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Optional

import requests
import yaml

REPO = "ne0-asref/ubds-database"
BRANCH = "main"
CACHE_TTL_SECONDS = 24 * 3600
_RETRIES = 3
_BACKOFF = (1, 2, 4)


class FetchError(Exception):
    """Raised when fetching boards fails and no usable cache exists."""


# ---------- cache dir ----------

def cache_dir() -> Path:
    env = os.environ.get("DBF_CACHE_DIR")
    if env:
        p = Path(env)
    else:
        p = Path.home() / ".devboardfinder" / "boards"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _yaml_files(d: Path) -> list[Path]:
    return sorted(d.glob("*.ubds.yaml"))


def cache_mtime() -> Optional[float]:
    files = _yaml_files(cache_dir())
    if not files:
        return None
    return max(f.stat().st_mtime for f in files)


def cache_age_seconds() -> Optional[float]:
    m = cache_mtime()
    if m is None:
        return None
    return time.time() - m


def cache_is_fresh() -> bool:
    age = cache_age_seconds()
    if age is None:
        return False
    return age < CACHE_TTL_SECONDS


def cache_board_count() -> int:
    return len(_yaml_files(cache_dir()))


# ---------- loading ----------

def boards_source_dir() -> Path:
    """Resolve the directory load_boards() reads from (override or cache)."""
    override = os.environ.get("DBF_BOARDS_DIR")
    return Path(override) if override else cache_dir()


def is_empty_cache() -> bool:
    """True if the boards source dir exists but contains no *.ubds.yaml files."""
    d = boards_source_dir()
    return d.exists() and not _yaml_files(d)


def load_boards() -> list[dict]:
    """Load every cached UBDS YAML as parsed dicts. Does NOT fetch."""
    override = os.environ.get("DBF_BOARDS_DIR")
    base = Path(override) if override else cache_dir()
    out: list[dict] = []
    for f in sorted(base.glob("*.ubds.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


# ---------- fetching ----------

def _auth_headers() -> dict:
    token = os.environ.get("DBF_REPO_TOKEN")
    h = {"Accept": "application/vnd.github+json", "User-Agent": "dbf-cli"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get_with_retry(url: str, headers: dict) -> requests.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(_RETRIES):
        try:
            r = requests.get(url, headers=headers, timeout=30)
            if 500 <= r.status_code < 600:
                last_exc = FetchError(f"HTTP {r.status_code} from {url}")
                if attempt < _RETRIES - 1:
                    time.sleep(_BACKOFF[attempt])
                    continue
                return r
            return r
        except requests.ConnectionError as e:
            last_exc = e
            if attempt < _RETRIES - 1:
                time.sleep(_BACKOFF[attempt])
                continue
            raise FetchError(f"connection error: {e}") from e
    # exhausted retries on 5xx
    raise FetchError(str(last_exc) if last_exc else "unknown fetch error")


def fetch_boards() -> None:
    """Fetch all boards/*.ubds.yaml from the repo into the cache dir."""
    headers = _auth_headers()
    tree_url = f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"
    r = _get_with_retry(tree_url, headers)
    if r.status_code == 404:
        raise FetchError(f"{REPO} not reachable (HTTP 404)")
    if r.status_code >= 400:
        raise FetchError(f"GitHub tree API returned HTTP {r.status_code}")

    try:
        payload = r.json()
    except ValueError as e:
        raise FetchError(f"invalid JSON from tree API: {e}") from e

    entries = payload.get("tree", []) or []
    targets = [
        e for e in entries
        if e.get("type") == "blob"
        and isinstance(e.get("path"), str)
        and e["path"].startswith("boards/")
        and e["path"].endswith(".ubds.yaml")
    ]

    dest = cache_dir()
    # Stage every download into a sibling temp directory first. Only after
    # all downloads succeed do we move files into the real cache. This
    # prevents partial-failure from leaving the cache half-updated.
    staging = dest.parent / f".boards.incoming.{os.getpid()}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    try:
        for entry in targets:
            path = entry["path"]
            raw_url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{path}"
            rr = _get_with_retry(raw_url, headers)
            if rr.status_code != 200:
                raise FetchError(f"failed to fetch {path}: HTTP {rr.status_code}")
            basename = os.path.basename(path)
            (staging / basename).write_bytes(rr.content)
        # All downloads succeeded — promote into cache atomically per file.
        for staged in staging.iterdir():
            os.replace(staged, dest / staged.name)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def ensure_cache(force: bool = False) -> None:
    """Make sure the cache is populated and fresh."""
    have_cache = cache_board_count() > 0
    if not force and cache_is_fresh():
        return
    try:
        fetch_boards()
    except (FetchError, requests.RequestException) as e:
        if have_cache:
            import sys
            print(f"warning: refresh failed ({e}); using cached boards", file=sys.stderr)
            return
        raise FetchError(str(e)) from e


def clear_cache() -> None:
    d = cache_dir()
    if d.exists():
        shutil.rmtree(d)
