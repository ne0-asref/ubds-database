"""`dbf import platformio` command implementation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml

from .pio_field_map import map_pio_to_ubds


def _slug_from_filename(p: Path) -> str:
    return p.stem.replace("_", "-")


def _resolve_output_path(out_dir: Path, slug: str) -> Path:
    base = out_dir / f"{slug}.ubds.yaml"
    if not base.exists():
        return base
    n = 2
    while True:
        candidate = out_dir / f"{slug}-imported-{n}.ubds.yaml"
        if not candidate.exists():
            return candidate
        n += 1


def _collect_inputs(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(p for p in path.glob("*.json") if p.is_file())
    return [path]


def _import_one(src: Path, out_dir: Path) -> tuple[Path | None, str | None]:
    """Return (written_path, error). Exactly one is non-None."""
    try:
        pio = json.loads(src.read_text())
    except (OSError, json.JSONDecodeError) as e:
        return None, f"parse error: {e}"
    if not isinstance(pio, dict):
        return None, "expected JSON object at top level"

    slug = _slug_from_filename(src)
    out_path = _resolve_output_path(out_dir, slug)
    # If collision suffix kicked in, the slug field should reflect it.
    final_slug = out_path.name.removesuffix(".ubds.yaml")

    source_url = pio.get("url") or src.resolve().as_uri()
    board = map_pio_to_ubds(pio, source_url=source_url, slug=final_slug)
    out_path.write_text(yaml.safe_dump(board, sort_keys=False))
    return out_path, None


@click.command("platformio")
@click.argument("path", required=True, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output-dir",
    default="./imported-boards/",
    show_default=True,
    type=click.Path(path_type=Path),
    help="Where to write generated UBDS YAML files.",
)
def import_platformio_cmd(path: Path, output_dir: Path) -> None:
    """Import PlatformIO board JSON (file or directory) into UBDS YAML."""
    inputs = _collect_inputs(path)
    if not inputs:
        click.echo("no PlatformIO JSON files found")
        click.echo("imported 0, skipped 0")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    imported = 0
    skipped = 0
    for src in inputs:
        written, err = _import_one(src, output_dir)
        if err is not None:
            skipped += 1
            click.echo(f"skip {src}: {err}")
            continue
        imported += 1
        click.echo(f"wrote {written}")

    click.echo(f"imported {imported}, skipped {skipped}")
    if imported == 0 and skipped > 0:
        sys.exit(1)
