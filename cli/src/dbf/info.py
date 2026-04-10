"""`dbf info <slug>` — show details for a single board."""
from __future__ import annotations

import json as _json
import os
import sys
from pathlib import Path
from typing import Optional

import click
import yaml

from . import data as _data


def _find_board_file(slug: str) -> Optional[Path]:
    override = os.environ.get("DBF_BOARDS_DIR")
    base = Path(override) if override else _data.cache_dir()
    filename_match: Optional[Path] = None
    for f in sorted(base.glob("*.ubds.yaml")):
        # Filename-based fallback so corrupt YAMLs still surface a clean
        # error instead of "no board with slug ...".
        if f.name == f"{slug}.ubds.yaml":
            filename_match = f
        try:
            text = f.read_text(encoding="utf-8")
            data = yaml.safe_load(text)
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(data, dict) and data.get("slug") == slug:
            return f
    return filename_match


def _join(items, key=None) -> str:
    if not items:
        return "\u2014"
    out = []
    for it in items:
        if key and isinstance(it, dict):
            v = it.get(key)
            if v is not None:
                out.append(str(v))
        else:
            out.append(str(it))
    return ", ".join(out) if out else "\u2014"


def _render(board: dict) -> str:
    lines: list[str] = []
    _na = "\u2014"
    name = board.get("name", "?")
    slug = board.get("slug", "?")
    lines.append(f"{name}  ({slug})")
    lines.append("=" * max(len(lines[0]), 8))
    lines.append(f"manufacturer:   {board.get('manufacturer', _na)}")

    # processing → architecture, ram, flash
    arches: list[str] = []
    ram_kb = None
    flash_kb = None
    for proc in board.get("processing", []) or []:
        for core in proc.get("cpu_cores", []) or []:
            a = core.get("architecture")
            if a:
                arches.append(str(a))
        mem = proc.get("memory") or {}
        if ram_kb is None and mem.get("ram_kb") is not None:
            ram_kb = mem.get("ram_kb")
        if flash_kb is None and mem.get("flash_kb") is not None:
            flash_kb = mem.get("flash_kb")

    lines.append(f"architecture:   {', '.join(arches) if arches else _na}")
    lines.append(f"ram:            {ram_kb if ram_kb is not None else _na} KB")
    lines.append(f"flash:          {flash_kb if flash_kb is not None else _na} KB")

    wireless = board.get("wireless", []) or []
    lines.append(f"wireless:       {_join(wireless, 'protocol')}")

    sw = board.get("software") or {}
    lines.append(f"frameworks:     {_join(sw.get('frameworks'), 'name')}")
    lines.append(f"languages:      {_join(sw.get('languages'), 'name')}")

    meta = board.get("meta") or {}
    last_verified = meta.get("last_verified")
    lines.append(f"last_verified:  {last_verified if last_verified else _na}")

    return "\n".join(lines)


@click.command("info")
@click.argument("slug", required=True)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.option("--raw", is_flag=True, help="Print raw YAML source verbatim.")
def info_cmd(slug: str, as_json: bool, raw: bool) -> None:
    """Show details for a single board by slug."""
    f = _find_board_file(slug)
    if f is None:
        if _data.is_empty_cache():
            from .search import _emit_empty_cache
            _emit_empty_cache(as_json)
            sys.exit(2)
        click.echo(f"No board with slug {slug}.", err=True)
        sys.exit(1)

    try:
        text = f.read_text(encoding="utf-8")
        board = yaml.safe_load(text)
    except (OSError, yaml.YAMLError) as e:
        click.echo(f"error: cannot read board file: {f}: {e}", err=True)
        sys.exit(1)

    if raw:
        click.echo(text)
        return
    if as_json:
        click.echo(_json.dumps(board, indent=2, sort_keys=True, default=str))
        return
    click.echo(_render(board))
