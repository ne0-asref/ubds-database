"""dbf search — filter the cached board catalog.

Filter table is locked in artifacts/build/c3-cli/spec.md §"Search filters".
Multiple flags AND together; repeated values for the same flag OR together.
"""
from __future__ import annotations

import json as _json
import os
import sys
from typing import Any, Iterable

import click

from . import data as _data

EMPTY_CACHE_MSG = (
    "No boards in local cache. "
    "Run `dbf cache update` to fetch the latest boards from ubds-database."
)


def _emit_empty_cache(as_json: bool) -> None:
    if as_json:
        click.echo(_json.dumps({"error": "empty_cache", "message": EMPTY_CACHE_MSG}))
    else:
        click.echo(EMPTY_CACHE_MSG, err=True)


# ---------- helpers ----------

def _as_list(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _processing(b: dict) -> list[dict]:
    return _as_list(b.get("processing"))


def _all_cpu_cores(b: dict) -> list[dict]:
    out: list[dict] = []
    for p in _processing(b):
        if isinstance(p, dict):
            out.extend(_as_list(p.get("cpu_cores")))
    return out


def _wireless_protocols(b: dict) -> list[str]:
    return [
        str(w.get("protocol", "")).lower()
        for w in _as_list(b.get("wireless"))
        if isinstance(w, dict)
    ]


def _icontains(haystack: str, needle: str) -> bool:
    return needle.lower() in (haystack or "").lower()


# ---------- predicates ----------

def _filter_name(b: dict, val: str) -> bool:
    return _icontains(str(b.get("name", "")), val)


def _filter_manufacturer(b: dict, val: str) -> bool:
    return _icontains(str(b.get("manufacturer", "")), val)


def _filter_board_type(b: dict, vals: tuple[str, ...]) -> bool:
    bts = _as_list(b.get("board_type"))
    return any(v in bts for v in vals)


def _filter_architecture(b: dict, vals: tuple[str, ...]) -> bool:
    archs = [str(c.get("architecture", "")) for c in _all_cpu_cores(b) if isinstance(c, dict)]
    return any(any(_icontains(a, v) for a in archs) for v in vals)


def _has_protocol(b: dict, name: str) -> bool:
    return name in _wireless_protocols(b)


def _filter_no_wireless(b: dict) -> bool:
    return len(_as_list(b.get("wireless"))) == 0


def _filter_framework(b: dict, vals: tuple[str, ...]) -> bool:
    sw = b.get("software") or {}
    fws = [str(f.get("name", "")) for f in _as_list(sw.get("frameworks")) if isinstance(f, dict)]
    return any(any(_icontains(f, v) for f in fws) for v in vals)


def _filter_language(b: dict, vals: tuple[str, ...]) -> bool:
    sw = b.get("software") or {}
    langs = [str(l.get("name", "")) for l in _as_list(sw.get("languages")) if isinstance(l, dict)]
    return any(any(_icontains(l, v) for l in langs) for v in vals)


def _any_mem(b: dict, key: str, predicate) -> bool:
    for p in _processing(b):
        mem = (p or {}).get("memory") or {}
        v = mem.get(key)
        if isinstance(v, (int, float)) and predicate(v):
            return True
    return False


def _any_core(b: dict, key: str, predicate) -> bool:
    for c in _all_cpu_cores(b):
        v = (c or {}).get(key)
        if isinstance(v, (int, float)) and predicate(v):
            return True
    return False


def _filter_tag(b: dict, vals: tuple[str, ...]) -> bool:
    tags = _as_list(b.get("tags"))
    return any(v in tags for v in vals)


def _filter_use_case(b: dict, vals: tuple[str, ...]) -> bool:
    ucs = _as_list(b.get("use_cases"))
    return any(v in ucs for v in vals)


def _filter_form_factor(b: dict, vals: tuple[str, ...]) -> bool:
    phys = b.get("physical") or {}
    ffs = _as_list(phys.get("form_factor"))
    return any(v in ffs for v in vals)


def _filter_difficulty(b: dict, val: str) -> bool:
    return b.get("difficulty_level") == val


def _filter_has_sensor(b: dict) -> bool:
    sw = b.get("software") or {}
    libs = _as_list(sw.get("libraries"))
    for lib in libs:
        if isinstance(lib, dict) and "sensor" in str(lib.get("category", "")).lower():
            return True
    return "sensors" in _as_list(b.get("tags"))


def _filter_has_display(b: dict) -> bool:
    return "display" in _as_list(b.get("tags"))


def _filter_verified(b: dict) -> bool:
    return bool(((b.get("meta") or {}).get("verified")) is True)


def _filter_community_reviewed(b: dict) -> bool:
    return bool(((b.get("meta") or {}).get("community_reviewed")) is True)


# ---------- key specs string ----------

def _key_specs(b: dict) -> str:
    arch = "—"
    clock = None
    ram = None
    flash = None
    cores = _all_cpu_cores(b)
    if cores:
        c0 = cores[0]
        if isinstance(c0, dict):
            arch = str(c0.get("architecture", arch))
            clock = c0.get("clock_mhz")
    procs = _processing(b)
    if procs:
        mem = (procs[0] or {}).get("memory") or {}
        ram = mem.get("ram_kb")
        flash = mem.get("flash_kb")
    parts = [arch]
    parts.append(f"{clock}MHz" if isinstance(clock, (int, float)) else "—MHz")
    parts.append(f"{ram}KB RAM" if isinstance(ram, (int, float)) else "— RAM")
    parts.append(f"{flash}KB flash" if isinstance(flash, (int, float)) else "— flash")
    return f"{parts[0]} {parts[1]} / {parts[2]} / {parts[3]}"


# ---------- click command ----------

@click.command("search")
@click.option("--name", "name", default=None)
@click.option("--manufacturer", "manufacturer", default=None)
@click.option("--board-type", "board_type", multiple=True)
@click.option("--architecture", "architecture", multiple=True)
@click.option("--wifi", is_flag=True)
@click.option("--ble", is_flag=True)
@click.option("--lora", is_flag=True)
@click.option("--thread", is_flag=True)
@click.option("--zigbee", is_flag=True)
@click.option("--cellular", is_flag=True)
@click.option("--no-wireless", "no_wireless", is_flag=True)
@click.option("--framework", "framework", multiple=True)
@click.option("--language", "language", multiple=True)
@click.option("--ram-min", "ram_min", type=int, default=None)
@click.option("--ram-max", "ram_max", type=int, default=None)
@click.option("--flash-min", "flash_min", type=int, default=None)
@click.option("--flash-max", "flash_max", type=int, default=None)
@click.option("--clock-min", "clock_min", type=int, default=None)
@click.option("--cores-min", "cores_min", type=int, default=None)
@click.option("--tag", "tag", multiple=True)
@click.option("--use-case", "use_case", multiple=True)
@click.option("--form-factor", "form_factor", multiple=True)
@click.option("--difficulty", "difficulty", default=None)
@click.option("--has-sensor", "has_sensor", is_flag=True)
@click.option("--has-display", "has_display", is_flag=True)
@click.option("--verified", "verified", is_flag=True)
@click.option("--community-reviewed", "community_reviewed", is_flag=True)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable result list.")
def search_cmd(**kw):
    """Search the board catalog by criteria."""
    as_json = kw.pop("as_json")

    # Best-effort cache hydrate (only if not using DBF_BOARDS_DIR override).
    if not os.environ.get("DBF_BOARDS_DIR"):
        try:
            _data.ensure_cache(force=False)
        except Exception as e:
            print(f"warning: cache refresh failed: {e}", file=sys.stderr)

    boards = _data.load_boards()
    if not boards and _data.is_empty_cache():
        _emit_empty_cache(as_json)
        sys.exit(2)
    matches = [b for b in boards if _matches(b, kw)]
    matches.sort(key=lambda b: str(b.get("slug", "")))

    if as_json:
        click.echo(_json.dumps(matches, indent=2, sort_keys=True, default=str))
        sys.exit(0)

    if not matches:
        click.echo("No boards match.")
        sys.exit(0)

    # Render table via rich
    try:
        from rich.console import Console
        from rich.table import Table
        table = Table()
        table.add_column("slug")
        table.add_column("name")
        table.add_column("manufacturer")
        table.add_column("key specs")
        for b in matches:
            table.add_row(
                str(b.get("slug", "")),
                str(b.get("name", "")),
                str(b.get("manufacturer", "")),
                _key_specs(b),
            )
        Console().print(table)
    except Exception:
        # Fallback plain text
        click.echo("slug\tname\tmanufacturer\tkey specs")
        for b in matches:
            click.echo(
                f"{b.get('slug','')}\t{b.get('name','')}\t{b.get('manufacturer','')}\t{_key_specs(b)}"
            )
    sys.exit(0)


def _matches(b: dict, kw: dict) -> bool:
    if kw.get("name") and not _filter_name(b, kw["name"]):
        return False
    if kw.get("manufacturer") and not _filter_manufacturer(b, kw["manufacturer"]):
        return False
    if kw.get("board_type") and not _filter_board_type(b, kw["board_type"]):
        return False
    if kw.get("architecture") and not _filter_architecture(b, kw["architecture"]):
        return False
    if kw.get("wifi") and not _has_protocol(b, "wifi"):
        return False
    if kw.get("ble") and not _has_protocol(b, "ble"):
        return False
    if kw.get("lora") and not _has_protocol(b, "lora"):
        return False
    if kw.get("thread") and not _has_protocol(b, "thread"):
        return False
    if kw.get("zigbee") and not _has_protocol(b, "zigbee"):
        return False
    if kw.get("cellular") and not _has_protocol(b, "cellular"):
        return False
    if kw.get("no_wireless") and not _filter_no_wireless(b):
        return False
    if kw.get("framework") and not _filter_framework(b, kw["framework"]):
        return False
    if kw.get("language") and not _filter_language(b, kw["language"]):
        return False
    if kw.get("ram_min") is not None and not _any_mem(b, "ram_kb", lambda v: v >= kw["ram_min"]):
        return False
    if kw.get("ram_max") is not None and not _any_mem(b, "ram_kb", lambda v: v <= kw["ram_max"]):
        return False
    if kw.get("flash_min") is not None and not _any_mem(b, "flash_kb", lambda v: v >= kw["flash_min"]):
        return False
    if kw.get("flash_max") is not None and not _any_mem(b, "flash_kb", lambda v: v <= kw["flash_max"]):
        return False
    if kw.get("clock_min") is not None and not _any_core(b, "clock_mhz", lambda v: v >= kw["clock_min"]):
        return False
    if kw.get("cores_min") is not None and not _any_core(b, "count", lambda v: v >= kw["cores_min"]):
        return False
    if kw.get("tag") and not _filter_tag(b, kw["tag"]):
        return False
    if kw.get("use_case") and not _filter_use_case(b, kw["use_case"]):
        return False
    if kw.get("form_factor") and not _filter_form_factor(b, kw["form_factor"]):
        return False
    if kw.get("difficulty") and not _filter_difficulty(b, kw["difficulty"]):
        return False
    if kw.get("has_sensor") and not _filter_has_sensor(b):
        return False
    if kw.get("has_display") and not _filter_has_display(b):
        return False
    if kw.get("verified") and not _filter_verified(b):
        return False
    if kw.get("community_reviewed") and not _filter_community_reviewed(b):
        return False
    return True
