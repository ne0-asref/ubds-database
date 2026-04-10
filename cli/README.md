# dbf — Universal Board Description Standard CLI

Pip-installable Python CLI for validating, searching, and importing UBDS
(Universal Board Description Standard) board descriptions.

`dbf` is the reference implementation of UBDS v1.1. Use it to lint board YAML
files, search a local cache of boards by capability, inspect details, and
import boards from existing ecosystems (e.g. PlatformIO).

## Install

From a checkout of this repo:

```bash
cd cli
python3 -m venv .venv
.venv/bin/pip install -e .
```

This installs the `dbf` entry point on your `PATH` (within the venv).

### First run

`dbf` ships without bundled boards. After installing, run `dbf cache update` to
fetch the latest boards from the public `ubds-database` repository. Subsequent
commands read from the local cache (`~/.devboardfinder/boards/`). Re-run
`dbf cache update` periodically to pull upstream changes — the cache has a 24h
TTL so most commands will trigger an auto-refresh on their own.

## Quick start

### 1. Confirm install + schema version

```bash
dbf --version
# dbf 0.1.0 (UBDS schema v1.1)
```

### 2. Validate a board YAML against UBDS v1.0

```bash
dbf validate path/to/board.ubds.yaml
```

Exit code is `0` on success and `1` on any schema or lint error. Add `--json`
for machine-readable output, or `--fix` to auto-correct safe issues
(trailing whitespace, tabs).

### 3. Search the local board cache by capability

```bash
dbf search --wifi --ble --ram-min 256
```

Filters compose with AND. Point at a custom directory with
`DBF_BOARDS_DIR=/path/to/boards`.

### 4. Inspect a single board

```bash
dbf info esp32-s3-devkitc-1
```

Add `--json` for the parsed document or `--raw` for the original YAML.

### 5. Import a board from PlatformIO

```bash
dbf import platformio pio.json --output-dir imported/
```

Reads a `pio boards --json` payload (file or directory of files) and emits
UBDS YAML stubs into `imported/`.

### 6. Refresh the local board cache

```bash
dbf cache update
```

Pulls the latest published boards from the `ubds-database` repository. See
also `dbf cache info` and `dbf cache clear`.

## Commands

| Command | Purpose |
|---|---|
| `dbf validate` | Lint a UBDS YAML file against schema v1.1 |
| `dbf search` | Filter the local board cache by capability |
| `dbf info` | Show details for a single board by slug |
| `dbf import platformio` | Convert PlatformIO board JSON to UBDS YAML |
| `dbf cache` | Manage the local board cache (`update`/`info`/`clear`) |

Run `dbf <command> --help` for full flag reference.
