"""C3 CLI surface drift guardrail. Task 1 covers C1 + version test only."""
from dbf.cli import main


def test_top_level_help_lists_all_subcommands(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    out = result.output
    for sub in ("validate", "search", "info", "import", "cache", "add-image"):
        assert sub in out, f"missing subcommand {sub!r} in --help output:\n{out}"


def test_version_prints_cli_and_schema(runner):
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "dbf 0.1.0" in result.output
    assert "UBDS schema v1.1" in result.output


# C2 — validate surface
def test_validate_help_lists_fix_and_json(runner):
    result = runner.invoke(main, ["validate", "--help"])
    assert result.exit_code == 0
    assert "--fix" in result.output
    assert "--json" in result.output


# C3 — search surface: covered by SR20 in test_search.py; skipped here.


# C4 — info surface
def test_info_help_lists_json_and_raw(runner):
    result = runner.invoke(main, ["info", "--help"])
    assert result.exit_code == 0
    assert "--json" in result.output
    assert "--raw" in result.output


# C5 — cache surface
def test_cache_help_lists_subcommands(runner):
    result = runner.invoke(main, ["cache", "--help"])
    assert result.exit_code == 0
    for sub in ("clear", "info", "update"):
        assert sub in result.output, f"missing cache subcommand {sub!r}"


# C6 — import platformio surface
def test_import_platformio_help_lists_output_dir(runner):
    result = runner.invoke(main, ["import", "platformio", "--help"])
    assert result.exit_code == 0
    assert "--output-dir" in result.output


# C7 — top-level surface lock: ONLY locked subcommands present
def test_top_level_help_only_locked_subcommands(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    locked = {"validate", "search", "info", "import", "cache", "add-image"}
    # Parse the Commands: section to extract command names.
    lines = result.output.splitlines()
    in_commands = False
    found = set()
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("commands"):
            in_commands = True
            continue
        if in_commands:
            if not line.startswith(" "):
                if stripped == "":
                    continue
                break
            parts = stripped.split()
            if parts:
                found.add(parts[0])
    assert found == locked, f"surface drift: expected {locked}, got {found}"
