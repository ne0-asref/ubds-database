"""Click CLI entry point for dbf."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from dbf import __version__
from dbf.data import find_boards_dir
from dbf.validate import validate_board, apply_fixes
from dbf.search import load_boards, search_boards
from dbf.info import get_board_info
from dbf.importers.platformio import convert_platformio_file, convert_platformio_directory

console = Console()
SCHEMA_DEFAULT = str(Path(__file__).parent.parent.parent.parent / "spec" / "ubds-v1.schema.json")


@click.group()
@click.version_option(version=__version__)
def cli():
    """dbf — DevBoardFinder CLI for the Universal Board Description Standard."""
    pass


# ── validate ──


@cli.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--schema", default=SCHEMA_DEFAULT, help="Path to JSON Schema file.")
@click.option("--fix", is_flag=True, help="Auto-fix simple issues (whitespace, casing).")
def validate(files, schema, fix):
    """Validate board YAML files against the UBDS JSON Schema."""
    has_errors = False

    for file_path in files:
        if fix:
            fixes = apply_fixes(file_path)
            for f in fixes:
                console.print(f"  [green]✓[/green] {f}", highlight=False)

        errors = validate_board(file_path, schema)

        if errors:
            has_errors = True
            console.print(f"\n[red]✗[/red] [bold]{file_path}[/bold]")
            for err in errors:
                _print_error(err)
        else:
            console.print(f"[green]✓[/green] [bold]{file_path}[/bold]")

    if has_errors:
        sys.exit(1)


def _print_error(err):
    """Print a single validation error in Elm style."""
    console.print(f"\n  [red]──[/red] {err.field}")
    console.print(f"  {err.message}")
    if err.expected:
        console.print(f"  [dim]Expected:[/dim] {err.expected}")
    if err.got:
        console.print(f"  [dim]Got:[/dim]      {err.got}")
    if err.fix_suggestion:
        console.print(f"  [yellow]Hint:[/yellow]     {err.fix_suggestion}")


# ── search ──


@cli.command()
@click.option("--boards-dir", default=None, help="Path to boards directory.")
@click.option("--wifi", is_flag=True, help="Filter boards with WiFi.")
@click.option("--bluetooth", is_flag=True, help="Filter boards with Bluetooth.")
@click.option("--rust", is_flag=True, help="Filter boards with Rust support.")
@click.option("--manufacturer", default=None, help="Filter by manufacturer name.")
@click.option("--type", "board_type", default=None, help="Filter by board type (MCU, SBC, etc).")
@click.option("--architecture", default=None, help="Filter by CPU architecture.")
@click.option("--framework", default=None, help="Filter by framework name.")
@click.option("--language", default=None, help="Filter by programming language.")
@click.option("--difficulty", default=None, type=click.Choice(["beginner", "intermediate", "advanced"]))
@click.option("--max-price", default=None, type=float, help="Maximum price in USD.")
def search(boards_dir, wifi, bluetooth, rust, manufacturer, board_type,
           architecture, framework, language, difficulty, max_price):
    """Search boards by criteria."""
    bd = find_boards_dir(boards_dir)
    boards = load_boards(bd)

    if not boards:
        console.print("[yellow]No boards found.[/yellow] Run from a directory with boards/ or specify --boards-dir.")
        return

    results = search_boards(
        boards,
        wifi=wifi,
        bluetooth=bluetooth,
        rust=rust,
        manufacturer=manufacturer,
        board_type=board_type,
        architecture=architecture,
        framework=framework,
        language=language,
        difficulty=difficulty,
        max_price=max_price,
    )

    if not results:
        console.print("[dim]No boards match your filters.[/dim]")
        return

    table = Table(title=f"{len(results)} board(s) found")
    table.add_column("Name", style="bold")
    table.add_column("Manufacturer")
    table.add_column("Type")
    table.add_column("Architecture")
    table.add_column("Price")

    for board in results:
        arch = ""
        for pe in board.get("processing", []):
            for core in pe.get("cpu_cores", []):
                arch = core.get("architecture", "")
                break
            if arch:
                break

        price = board.get("pricing", {}).get("msrp_usd")
        price_str = f"${price:.0f}" if price else "—"

        table.add_row(
            board["name"],
            board.get("manufacturer", ""),
            ", ".join(board.get("board_type", [])),
            arch,
            price_str,
        )

    console.print(table)


# ── info ──


@cli.command()
@click.argument("slug")
@click.option("--boards-dir", default=None, help="Path to boards directory.")
def info(slug, boards_dir):
    """Display details for a board by slug."""
    bd = find_boards_dir(boards_dir)
    board = get_board_info(slug, bd)

    if board is None:
        console.print(f"[red]Board '{slug}' not found.[/red]")
        sys.exit(1)

    # Header
    console.print(Panel(
        f"[bold]{board['name']}[/bold]\n"
        f"by {board.get('manufacturer', 'Unknown')}",
        title=board["slug"],
        border_style="green",
    ))

    # Quick facts
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="dim")
    table.add_column("Value")

    table.add_row("Type", ", ".join(board.get("board_type", [])))
    table.add_row("Status", board.get("status", "—"))
    table.add_row("Difficulty", board.get("difficulty_level", "—"))

    # Processing
    for pe in board.get("processing", []):
        for core in pe.get("cpu_cores", []):
            table.add_row("CPU", f"{core.get('architecture', '?')} @ {core.get('clock_mhz', '?')} MHz × {core.get('count', 1)}")
        mem = pe.get("memory", {})
        if mem.get("ram_kb"):
            ram = mem["ram_kb"]
            ram_str = f"{ram} KB" if ram < 1024 else f"{ram // 1024} MB" if ram < 1048576 else f"{ram // 1048576} GB"
            table.add_row("RAM", ram_str)
        if mem.get("flash_kb"):
            flash = mem["flash_kb"]
            flash_str = f"{flash} KB" if flash < 1024 else f"{flash // 1024} MB"
            table.add_row("Flash", flash_str)

    # Wireless
    wireless = board.get("wireless", [])
    if wireless:
        protos = [w.get("protocol", "?") for w in wireless]
        table.add_row("Wireless", ", ".join(protos))
    else:
        table.add_row("Wireless", "None")

    # Price
    price = board.get("pricing", {}).get("msrp_usd")
    if price:
        table.add_row("Price", f"${price:.2f}")

    console.print(table)

    # Software
    sw = board.get("software", {})
    langs = [l.get("name", "?") for l in sw.get("languages", [])]
    fws = [f.get("name", "?") for f in sw.get("frameworks", [])]
    if langs:
        console.print(f"\n[dim]Languages:[/dim] {', '.join(langs)}")
    if fws:
        console.print(f"[dim]Frameworks:[/dim] {', '.join(fws)}")


# ── import ──


@cli.group(name="import")
def import_group():
    """Import boards from external formats."""
    pass


@import_group.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("--output-dir", required=True, type=click.Path(), help="Output directory for UBDS YAML files.")
def platformio(source, output_dir):
    """Import PlatformIO board JSON to UBDS YAML."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    source_path = Path(source)

    if source_path.is_dir():
        results = convert_platformio_directory(source_path, output_path)
        console.print(f"[green]✓[/green] Imported {len(results)} board(s) from {source_path}")
        for r in results:
            console.print(f"  → {r.name}")
    else:
        result = convert_platformio_file(source_path, output_path)
        console.print(f"[green]✓[/green] Imported → {result.name}")
