"""dbf root Click command. Task 1 wires only the help/version surface;
real subcommand bodies land in subsequent tasks but their command nodes
must already exist so the locked surface in spec.md is testable today."""
from __future__ import annotations

import json as _json
import sys
import time
from pathlib import Path

import click

from . import __version__
from . import data as _data
from . import validate as _validate
from .errors import format_errors
from .importers.platformio import import_platformio_cmd as _import_platformio_cmd
from .info import info_cmd as _info_cmd
from .search import search_cmd as _search_cmd

SCHEMA_VERSION = "1.1"


def _print_version(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    if not value or ctx.resilient_parsing:
        return
    click.echo(f"dbf {__version__} (UBDS schema v{SCHEMA_VERSION})")
    ctx.exit()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--version",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_print_version,
    help="Show the dbf version and bundled UBDS schema version, then exit.",
)
def main() -> None:
    """dbf — validate, search, and import Universal Board Description files."""


# --- placeholder subcommands (real bodies land in later tasks) ---


def _resolve_image_root(path_arg: str) -> Path | None:
    """Infer the ubds-database repo root for ``dbf validate --check-images``.

    The user's argument may be the repo root, the ``boards/`` directory,
    or a single board YAML. Image checks always walk ``<root>/images/`` +
    ``<root>/boards/``, so we have to climb back to the repo root.

    Returns ``None`` when no sensible root can be inferred (e.g. isolated
    YAML outside a repo tree) — caller prints the actionable error.
    """
    p = Path(path_arg)
    if p.is_dir():
        # Case 1: caller passed the repo root directly.
        if (p / "images").is_dir() and (p / "boards").is_dir():
            return p
        # Case 2: caller passed the boards/ dir; images/ sits next to it.
        if p.name == "boards" and (p.parent / "images").is_dir():
            return p.parent
        return None
    if p.is_file():
        # File must live under <root>/boards/ for image checks to make sense.
        parent = p.parent
        if parent.name == "boards" and (parent.parent / "images").is_dir():
            return parent.parent
        return None
    return None


def _print_image_result(r: _validate.ImageCheckResult) -> None:
    """Render one :class:`ImageCheckResult` as an Elm-style block."""
    if r.severity == "error":
        header = "-- IMAGE VALIDATION ERROR " + "-" * 40
    else:
        header = "-- IMAGE WARNING " + "-" * 49
    click.echo(header)
    click.echo(f"  path:   {r.path}")
    click.echo(f"  rule:   {r.message}")
    click.echo("  remedy: see CONTRIBUTING.md §Adding a board image")
    click.echo("")


@main.command("validate")
@click.argument("path", required=True)
@click.option("--fix", is_flag=True, help="Auto-correct fixable issues in place.")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable error output.")
@click.option(
    "--check-images/--no-check-images",
    "check_images",
    default=None,
    help=(
        "Run board-image validation in addition to schema checks. "
        "Default: on for directories, off for single-file invocations."
    ),
)
def validate_cmd(path: str, fix: bool, as_json: bool, check_images: bool | None) -> None:
    """Validate a UBDS YAML file, glob, or directory."""
    paths = _validate.collect_paths(path)
    if not paths:
        click.echo("No YAML files found.")
        sys.exit(0)

    # Resolve the effective check_images choice:
    # - None (default)  → on iff arg is a directory.
    # - True / False    → honor the explicit flag.
    arg_is_dir = Path(path).is_dir()
    run_image_check = arg_is_dir if check_images is None else check_images

    if fix:
        for p in paths:
            report = _validate.apply_fixes(p)
            if report.modified:
                click.echo(f"fixed {p}:")
                for ch in report.changes:
                    click.echo(f"  - {ch}")
            else:
                click.echo(f"no changes: {p}")

    results = [_validate.validate_file(p) for p in paths]

    any_failed = False

    if as_json:
        out = []
        for r in results:
            errs = []
            for e in r.errors:
                errs.append({
                    "path": ".".join(str(x) for x in e.absolute_path) or "<root>",
                    "message": e.message,
                    "line": None,
                    "col": None,
                    "fix": e.validator,
                })
            if r.parse_error:
                errs.append({
                    "path": "<file>",
                    "message": r.parse_error,
                    "line": None,
                    "col": None,
                    "fix": "parse",
                })
            if r.version_level == "error":
                errs.append({
                    "path": "ubds_version",
                    "message": r.version_message,
                    "line": None,
                    "col": None,
                    "fix": "version",
                })
            if errs:
                any_failed = True
            out.append({"file": str(r.path), "errors": errs})
        click.echo(_json.dumps(out, indent=2, sort_keys=True))
    else:
        for r in results:
            if r.parse_error:
                any_failed = True
                click.echo(f"\u2717 {r.path}\n  parse error: {r.parse_error}")
                continue
            if r.errors:
                any_failed = True
                click.echo(format_errors(r.errors, r.yaml_text, str(r.path)))
            if r.version_level == "warn":
                click.echo(f"warning: {r.path}: {r.version_message}")
            elif r.version_level == "error":
                any_failed = True
                click.echo(f"\u2717 {r.path}: {r.version_message}")
            if r.ok:
                click.echo(f"\u2713 {r.path}")

    # Board-image validation (C21.2). Runs after schema checks so schema
    # errors and image errors never shadow each other.
    root: Path | None = _resolve_image_root(path) if run_image_check else None
    if run_image_check and root is None:
        if check_images is True:
            # Explicit opt-in but we can't find a root — tell the user.
            click.echo(
                "error: cannot locate images/ directory; run from repo "
                "root or pass a directory argument containing boards/ "
                "and images/.",
                err=True,
            )
            sys.exit(2)
        # Default mode on a directory with no images/ sibling — silently
        # skip. Legacy trees (tests, ad-hoc YAML dirs) still schema-validate.
        run_image_check = False

    if run_image_check and root is not None:
        image_results = _validate.check_images(root)
        # Rule 13 is directory-scoped. On single-file invocations it still runs
        # against the full boards/ tree via the resolved root, but contributors
        # running `--check-images` against one file may not expect cross-file
        # errors \u2014 so surface a one-line note the first time the flag is used
        # explicitly on a single file.
        if not arg_is_dir and check_images is True:
            click.echo(
                "note: --check-images on a single file runs cross-file "
                "checks (Rule 13) against the full boards/ tree."
            )

        errors_for_exit = [r for r in image_results if r.severity == "error"]
        warns = [r for r in image_results if r.severity == "warn"]
        if as_json:
            click.echo(_json.dumps(
                [
                    {
                        "path": str(r.path),
                        "severity": r.severity,
                        "message": r.message,
                    }
                    for r in image_results
                ],
                indent=2,
                sort_keys=True,
            ))
        else:
            for r in errors_for_exit:
                _print_image_result(r)
            for r in warns:
                _print_image_result(r)
        if errors_for_exit:
            any_failed = True

    sys.exit(1 if any_failed else 0)


main.add_command(_search_cmd)
main.add_command(_info_cmd)


@main.group("import")
def import_group() -> None:
    """Import boards from external catalogs."""


import_group.add_command(_import_platformio_cmd)


@main.group("cache")
def cache_group() -> None:
    """Manage the local board cache."""


@cache_group.command("clear")
def cache_clear_cmd() -> None:
    """Delete the local cache directory."""
    d = _data.cache_dir()
    _data.clear_cache()
    click.echo(f"cleared cache at {d}")


def _format_age(seconds: float) -> str:
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


@cache_group.command("info")
def cache_info_cmd() -> None:
    """Show cache age, board count, and last fetched time."""
    d = _data.cache_dir()
    count = _data.cache_board_count()
    mtime = _data.cache_mtime()
    click.echo(f"cache dir: {d}")
    click.echo(f"boards: {count}")
    if mtime is None:
        click.echo("last fetched: never")
        click.echo("age: n/a")
    else:
        age = _data.cache_age_seconds() or 0
        last = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
        click.echo(f"last fetched: {last}")
        click.echo(f"age: {_format_age(age)}")


@cache_group.command("update")
def cache_update_cmd() -> None:
    """Force a cache refresh, ignoring the 24h freshness timer."""
    try:
        _data.ensure_cache(force=True)
    except _data.FetchError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(1)
    n = _data.cache_board_count()
    click.echo(f"updated cache: {n} boards")


if __name__ == "__main__":  # pragma: no cover
    main()
