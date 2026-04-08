"""``dbf validate`` core logic.

Provides:
- ``collect_paths`` — expand a file/dir/glob argument into concrete YAML paths.
- ``validate_file`` — run jsonschema Draft7 validation on a single file and
  return a list of (ValidationError, yaml_text) tuples plus a version-check
  result so callers can render Elm-style error blocks.
- ``apply_fixes`` — perform the closed set of in-place autocorrections from
  spec.md §"--fix scope". Idempotent. Writes a ``.bak`` only when something
  actually changed.

The CLI command in ``cli.py`` glues these together with output formatting and
exit codes.
"""
from __future__ import annotations

import datetime as _dt
import glob as _glob
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from jsonschema import Draft7Validator, ValidationError, FormatChecker

from .schema import load_schema
from .vendor_map import normalize_vendor
from .version import check_version

# ---------------------------------------------------------------------------
# Path collection
# ---------------------------------------------------------------------------

YAML_SUFFIX = ".ubds.yaml"


def collect_paths(arg: str) -> List[Path]:
    """Expand ``arg`` (file, directory, or glob) into a sorted list of YAML files.

    - File: returned as-is (must end in ``.ubds.yaml`` to be considered).
    - Directory: walked recursively for ``*.ubds.yaml``.
    - Glob: expanded via :mod:`glob`.
    """
    p = Path(arg)
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(p.rglob(f"*{YAML_SUFFIX}"))
    # Treat as glob
    matches = sorted(Path(m) for m in _glob.glob(arg, recursive=True))
    return [m for m in matches if m.is_file()]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass
class FileValidation:
    path: Path
    yaml_text: Optional[str]
    parse_error: Optional[str]
    errors: List[ValidationError]
    version_level: str  # "ok" | "warn" | "error"
    version_message: str

    @property
    def ok(self) -> bool:
        return (
            self.parse_error is None
            and not self.errors
            and self.version_level != "error"
        )


_validator: Optional[Draft7Validator] = None


def _get_validator() -> Draft7Validator:
    global _validator
    if _validator is None:
        _validator = Draft7Validator(load_schema(), format_checker=FormatChecker())
    return _validator


def validate_file(path: Path) -> FileValidation:
    """Load + schema-validate a single board file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return FileValidation(
            path=path,
            yaml_text=None,
            parse_error=f"could not read file: {exc}",
            errors=[],
            version_level="error",
            version_message="unreadable",
        )

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return FileValidation(
            path=path,
            yaml_text=text,
            parse_error=f"YAML parse error: {exc}",
            errors=[],
            version_level="error",
            version_message="parse failed",
        )

    if not isinstance(data, dict):
        return FileValidation(
            path=path,
            yaml_text=text,
            parse_error="top-level YAML value is not a mapping",
            errors=[],
            version_level="error",
            version_message="not a mapping",
        )

    errors = sorted(_get_validator().iter_errors(data), key=lambda e: list(e.absolute_path))
    board_version = data.get("ubds_version", "")
    level, msg = check_version(str(board_version)) if board_version else ("error", "missing ubds_version")

    return FileValidation(
        path=path,
        yaml_text=text,
        parse_error=None,
        errors=errors,
        version_level=level,
        version_message=msg,
    )


# ---------------------------------------------------------------------------
# Fixes
# ---------------------------------------------------------------------------

@dataclass
class FixReport:
    file: Path
    changes: List[str] = field(default_factory=list)
    modified: bool = False


_KNOWN_PROTOCOLS = {
    "wifi",
    "ble",
    "bluetooth",
    "lora",
    "thread",
    "zigbee",
    "cellular",
}


def _strip_trailing_ws(lines: List[str]) -> Tuple[List[str], int]:
    n = 0
    out = []
    for line in lines:
        # Split off line ending, then rstrip only spaces/tabs from the body.
        if line.endswith("\r\n"):
            body, ending = line[:-2], "\r\n"
        elif line.endswith("\n"):
            body, ending = line[:-1], "\n"
        else:
            body, ending = line, ""
        stripped = body.rstrip(" \t")
        if stripped != body:
            n += 1
        out.append(stripped + ending)
    return out, n


def _convert_leading_tabs(lines: List[str]) -> Tuple[List[str], int]:
    n = 0
    out = []
    for line in lines:
        if line.endswith("\r\n"):
            body, ending = line[:-2], "\r\n"
        elif line.endswith("\n"):
            body, ending = line[:-1], "\n"
        else:
            body, ending = line, ""
        i = 0
        while i < len(body) and body[i] == "\t":
            i += 1
        if i:
            out.append("  " * i + body[i:] + ending)
            n += 1
        else:
            out.append(line)
    return out, n


def _normalize_manufacturer_line(lines: List[str]) -> Tuple[List[str], Optional[str]]:
    pat = re.compile(r'^(\s*manufacturer:\s*)(?:"([^"]*)"|\'([^\']*)\'|([^\s#]+))(\s*(?:#.*)?)\s*$')
    for i, line in enumerate(lines):
        m = pat.match(line.rstrip("\n"))
        if not m:
            continue
        prefix, dq, sq, bare, suffix = m.groups()
        current = dq if dq is not None else (sq if sq is not None else bare)
        canonical = normalize_vendor(current)
        if canonical:
            newline = f'{prefix}"{canonical}"{suffix or ""}'
            # preserve original line ending
            ending = "\n" if line.endswith("\n") else ""
            lines[i] = newline + ending
            return lines, f'manufacturer "{current}" -> "{canonical}"'
    return lines, None


def _lowercase_protocols(lines: List[str]) -> Tuple[List[str], int]:
    pat = re.compile(r'^(\s*-?\s*protocol:\s*)(?:"([^"]*)"|\'([^\']*)\'|([^\s#]+))(\s*(?:#.*)?)\s*$')
    n = 0
    for i, line in enumerate(lines):
        m = pat.match(line.rstrip("\n"))
        if not m:
            continue
        prefix, dq, sq, bare, suffix = m.groups()
        current = dq if dq is not None else (sq if sq is not None else bare)
        if current.lower() in _KNOWN_PROTOCOLS and current != current.lower():
            ending = "\n" if line.endswith("\n") else ""
            lines[i] = f"{prefix}{current.lower()}{suffix or ''}" + ending
            n += 1
    return lines, n


def _lowercase_named(lines: List[str], known: set[str]) -> Tuple[List[str], int]:
    """Lowercase ``- name: Foo`` entries whose lowercased value is in ``known``.

    Used for software.frameworks[].name and software.languages[].name.
    """
    pat = re.compile(r'^(\s*-?\s*name:\s*)(?:"([^"]*)"|\'([^\']*)\'|([^\s#]+))(\s*(?:#.*)?)\s*$')
    n = 0
    for i, line in enumerate(lines):
        m = pat.match(line.rstrip("\n"))
        if not m:
            continue
        prefix, dq, sq, bare, suffix = m.groups()
        current = dq if dq is not None else (sq if sq is not None else bare)
        if current.lower() in known and current != current.lower():
            ending = "\n" if line.endswith("\n") else ""
            lines[i] = f"{prefix}{current.lower()}{suffix or ''}" + ending
            n += 1
    return lines, n


_KNOWN_FRAMEWORKS = {
    "arduino", "platformio", "esp-idf", "zephyr", "mbed", "circuitpython",
    "micropython", "stm32cube", "nrf-connect", "tinygo", "ros2", "jetpack",
}
_KNOWN_LANGUAGES = {
    "c", "cpp", "c++", "python", "rust", "go", "javascript", "typescript",
    "java", "lua", "ada", "zig",
}


def _has_last_verified(text: str) -> bool:
    return re.search(r"^\s*last_verified\s*:", text, re.MULTILINE) is not None


def _has_meta(text: str) -> bool:
    return re.search(r"^meta\s*:", text, re.MULTILINE) is not None


def _inject_last_verified(lines: List[str], today: str) -> Tuple[List[str], bool]:
    """Inject ``last_verified: <today>`` under the existing ``meta:`` block.

    Looks for the line ``meta:`` and inserts a child line directly after it
    using 2-space indent. If no ``meta:`` block exists, does nothing (the
    schema requires meta anyway and the validator will surface that).
    """
    for i, line in enumerate(lines):
        if re.match(r"^meta\s*:\s*(?:#.*)?$", line.rstrip("\n")):
            indent = "  "
            new_line = f'{indent}last_verified: "{today}"\n'
            lines.insert(i + 1, new_line)
            return lines, True
    return lines, False


def apply_fixes(path: Path, *, assume_yes: Optional[bool] = None) -> FixReport:
    """Apply the closed set of autocorrections to ``path`` in place.

    Writes a ``.bak`` next to the original ONLY if something changed.
    Idempotent: a second invocation produces no further changes and leaves
    the existing ``.bak`` alone.
    """
    report = FixReport(file=path)

    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)

    lines, ws_count = _strip_trailing_ws(lines)
    if ws_count:
        report.changes.append(f"stripped trailing whitespace on {ws_count} line(s)")

    lines, tab_count = _convert_leading_tabs(lines)
    if tab_count:
        report.changes.append(f"converted leading tabs to spaces on {tab_count} line(s)")

    lines, mfr_change = _normalize_manufacturer_line(lines)
    if mfr_change:
        report.changes.append(mfr_change)

    lines, proto_count = _lowercase_protocols(lines)
    if proto_count:
        report.changes.append(f"lowercased {proto_count} wireless protocol value(s)")

    lines, fw_count = _lowercase_named(lines, _KNOWN_FRAMEWORKS)
    if fw_count:
        report.changes.append(f"lowercased {fw_count} framework name(s)")

    lines, lang_count = _lowercase_named(lines, _KNOWN_LANGUAGES)
    if lang_count:
        report.changes.append(f"lowercased {lang_count} language name(s)")

    new_text = "".join(lines)

    # last_verified injection (only if meta exists and last_verified missing)
    if _has_meta(new_text) and not _has_last_verified(new_text):
        if assume_yes is None:
            assume_yes = os.environ.get("DBF_FIX_ASSUME_YES") == "1"
        do_inject = assume_yes
        if not do_inject:
            try:
                import click as _click
                do_inject = _click.confirm(
                    f"{path}: meta.last_verified missing. Set to today's date?",
                    default=True,
                )
            except Exception:
                do_inject = False
        if do_inject:
            today = _dt.date.today().isoformat()
            lines2 = new_text.splitlines(keepends=True)
            lines2, injected = _inject_last_verified(lines2, today)
            if injected:
                new_text = "".join(lines2)
                report.changes.append(f"set meta.last_verified to {today}")

    if new_text != original:
        bak = path.with_suffix(path.suffix + ".bak")
        if not bak.exists():
            bak.write_text(original, encoding="utf-8")
        # Atomic write: stage to sibling .tmp, then os.replace.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(new_text, encoding="utf-8")
        import os as _os
        _os.replace(tmp, path)
        report.modified = True

    return report
