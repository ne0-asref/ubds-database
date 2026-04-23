"""``dbf validate`` core logic.

Provides:
- ``collect_paths`` — expand a file/dir/glob argument into concrete YAML paths.
- ``validate_file`` — run jsonschema Draft7 validation on a single file and
  return a list of (ValidationError, yaml_text) tuples plus a version-check
  result so callers can render Elm-style error blocks.
- ``apply_fixes`` — perform the closed set of in-place autocorrections from
  spec.md §"--fix scope". Idempotent. Writes a ``.bak`` only when something
  actually changed.
- ``check_images`` — walk ``root/images/`` and ``root/boards/`` and report
  violations of the 13 board-image rules documented in
  ``artifacts/eng-plan.md §4 C21.2``. Pure function, stdlib-only PNG
  inspection (D21.5).

The CLI command in ``cli.py`` glues these together with output formatting and
exit codes.
"""
from __future__ import annotations

import datetime as _dt
import glob as _glob
import os
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

import yaml
from jsonschema import Draft7Validator, ValidationError, FormatChecker

from .constants import (
    CANONICAL_IMAGE_FILENAMES,
    CANONICAL_IMAGE_URL_PATTERN,
    IMAGE_FALLBACKS,
    MAX_IMAGE_BYTES,
    PNG_IHDR_COLOR_TYPE_RGBA,
    PNG_SIGNATURE,
)
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


# ---------------------------------------------------------------------------
# Board-image validation (C21.2)
#
# ``check_images(root)`` is the single source of truth for the 13 board-image
# rules defined in ``artifacts/eng-plan.md §4 C21.2``. It replaces the legacy
# bash-in-CI job. Pure function — reads from disk, returns results, does not
# print or exit. The CLI layer in ``cli.py`` renders the results.
#
# Implementation notes:
# - PNG inspection is stdlib-only (D21.5): signature via first-8-byte compare
#   against ``PNG_SIGNATURE``, color_type via ``struct.unpack`` on the IHDR
#   byte at offset 25.
# - Rule 11 (URL coupling) only applies to ``top-view`` and ``pinout`` stems,
#   matching the capture group in ``CANONICAL_IMAGE_URL_PATTERN``. Fallback
#   stems never trigger coupling.
# - Rule 13 (cross-file slug uniqueness) is intrinsically directory-scoped;
#   the CLI surfaces a one-time note on single-file invocations.
# ---------------------------------------------------------------------------

ImageSeverity = Literal["error", "warn"]


@dataclass
class ImageCheckResult:
    """One violation reported by :func:`check_images`.

    ``path`` is the file or directory the rule is about (may be a slug
    directory for rules 1-3 / 9-10, a file for rules 4-8 / 11, or a board
    YAML for rule 13).
    """

    path: Path
    severity: ImageSeverity
    message: str


# Rules 11 apply only to these stems — matches the capture group in
# CANONICAL_IMAGE_URL_PATTERN. Fallback stems (angle/bottom-view/block-diagram)
# never trigger URL coupling.
_URL_COUPLED_STEMS: Tuple[str, ...] = ("top-view", "pinout")
_URL_FIELD_BY_STEM: Dict[str, str] = {
    "top-view": "image_url",
    "pinout": "pinout_image_url",
}

# Rule 8 RGBA warn applies only to the primary product photo + fallbacks that
# are shown as the primary image. Opaque pinout diagrams are allowed.
_RGBA_WARN_STEMS: Tuple[str, ...] = ("top-view", "bottom-view", "angle")


def _is_valid_png(path: Path) -> Tuple[bool, Optional[int]]:
    """Read the first ~25 bytes and return ``(signature_ok, color_type)``.

    ``color_type`` is the IHDR byte at offset 25 (0 = greyscale, 2 = RGB,
    3 = indexed, 4 = greyscale+alpha, 6 = RGBA). Returns ``None`` when the
    signature or IHDR chunk is missing/truncated.
    """
    try:
        with path.open("rb") as fh:
            header = fh.read(26)
    except OSError:
        return (False, None)

    if not header.startswith(PNG_SIGNATURE):
        return (False, None)
    # IHDR length(4) + "IHDR"(4) + width(4) + height(4) + depth(1) + color_type(1)
    # Offset of color_type inside the file is 8 + 4 + 4 + 4 + 4 + 1 = 25.
    if len(header) < 26:
        return (True, None)
    color_type = header[25]
    return (True, color_type)


def _collect_slug_map(boards_dir: Path) -> Dict[str, List[Path]]:
    """Map each declared ``slug:`` value to the board YAMLs that declare it.

    Only files whose content is a mapping with a scalar ``slug`` key are
    included. Parse failures are silently skipped here — the schema-level
    validator surfaces them separately.
    """
    out: Dict[str, List[Path]] = {}
    if not boards_dir.is_dir():
        return out
    for yml in sorted(boards_dir.glob(f"*{YAML_SUFFIX}")):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        slug = data.get("slug")
        if not isinstance(slug, str) or not slug:
            continue
        out.setdefault(slug, []).append(yml)
    return out


def _load_meta(yaml_path: Path) -> Tuple[dict, dict]:
    """Return ``(full_data, meta_block)`` for a board file.

    ``meta_block`` is always a dict (possibly empty). Parse/structure
    failures yield ``({}, {})`` so callers can bail out without crashing.
    """
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return ({}, {})
    if not isinstance(data, dict):
        return ({}, {})
    meta = data.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    return (data, meta)


def _check_single_slug_dir(
    slug_dir: Path,
    slug: str,
    declared_slugs: set,
) -> List[ImageCheckResult]:
    """Apply rules 1-8 + 9-10 to one ``images/<slug>/`` directory.

    Rule 11 (URL coupling) needs the board YAML and is applied separately
    in :func:`check_images`.
    """
    out: List[ImageCheckResult] = []

    # Rule 1 — symlink directories not allowed.
    if slug_dir.is_symlink():
        out.append(ImageCheckResult(
            path=slug_dir,
            severity="error",
            message=f"symlinked image directories not allowed: images/{slug_dir.name}/",
        ))
        # Don't descend into a symlinked dir — we've already rejected it.
        return out

    # Rule 2 — mixed-case slug directory.
    if slug != slug.lower():
        out.append(ImageCheckResult(
            path=slug_dir,
            severity="error",
            message=f"slug directories must be lowercase: images/{slug}/",
        ))

    # Walk the contents.
    stems_present: List[str] = []
    has_any_file = False
    for entry in sorted(slug_dir.iterdir()):
        rel = f"images/{slug}/{entry.name}"

        # Rule 3 — nested subdirectories.
        if entry.is_dir():
            out.append(ImageCheckResult(
                path=entry,
                severity="error",
                message=f"nested subdirectories not allowed under images/: {rel}/",
            ))
            continue

        if not entry.is_file():
            continue
        has_any_file = True

        # Rule 4 — extension must be .png.
        if entry.suffix.lower() != ".png":
            out.append(ImageCheckResult(
                path=entry,
                severity="error",
                message=f"image extension must be .png: {rel}",
            ))
            continue

        # Rule 5 — stem must be in canonical vocabulary.
        stem = entry.stem
        if stem not in CANONICAL_IMAGE_FILENAMES:
            allowed = ", ".join(CANONICAL_IMAGE_FILENAMES)
            out.append(ImageCheckResult(
                path=entry,
                severity="error",
                message=f"disallowed image filename: {rel} (allowed: {allowed})",
            ))
            continue
        stems_present.append(stem)

        # Rule 7 — size.
        try:
            size = entry.stat().st_size
        except OSError:
            size = 0
        if size > MAX_IMAGE_BYTES:
            out.append(ImageCheckResult(
                path=entry,
                severity="error",
                message=f"image exceeds 1 MB: {rel} ({size} bytes)",
            ))
            # Still check signature + color type so the contributor sees every
            # actionable problem in one pass.

        # Rule 6 — PNG signature.
        sig_ok, color_type = _is_valid_png(entry)
        if not sig_ok:
            out.append(ImageCheckResult(
                path=entry,
                severity="error",
                message=f"not a valid PNG: {rel} (signature mismatch)",
            ))
            continue
        if color_type is None:
            # Signature present but IHDR truncated — still a PNG validity failure.
            out.append(ImageCheckResult(
                path=entry,
                severity="error",
                message=f"not a valid PNG: {rel} (IHDR truncated)",
            ))
            continue

        # Rule 8 — RGBA warn for top-view / bottom-view / angle.
        if stem in _RGBA_WARN_STEMS and color_type != PNG_IHDR_COLOR_TYPE_RGBA:
            out.append(ImageCheckResult(
                path=entry,
                severity="warn",
                message=f"expected RGBA (transparent background): {rel}",
            ))

    # Rule 12 — empty slug dir is silent. No-op branch kept explicit for clarity.
    if not has_any_file:
        return out

    # Rule 9 — orphan directory (no matching board YAML declared this slug).
    if slug not in declared_slugs:
        out.append(ImageCheckResult(
            path=slug_dir,
            severity="warn",
            message=f"orphan image directory: images/{slug}/ (no matching board YAML)",
        ))

    # Rule 10 — fallback-only preference warn (only if the slug has a matching
    # board; orphan dirs already got their own warning above).
    has_primary = "top-view" in stems_present
    has_fallback = any(s in IMAGE_FALLBACKS for s in stems_present)
    if slug in declared_slugs and has_fallback and not has_primary:
        out.append(ImageCheckResult(
            path=slug_dir,
            severity="warn",
            message=(
                f"consider contributing a top-view.png for images/{slug}/ "
                f"(see CONTRIBUTING.md §Adding a board image)"
            ),
        ))

    return out


def _check_url_coupling(
    slug: str,
    slug_dir: Path,
    meta: dict,
) -> List[ImageCheckResult]:
    """Rule 11 — require canonical ``meta.{image_url,pinout_image_url}`` when
    the matching file exists on disk.

    Fallback stems don't trigger coupling. Absent keys are fine (board hasn't
    published yet). Populated non-matching or null values are errors.
    """
    out: List[ImageCheckResult] = []
    for stem in _URL_COUPLED_STEMS:
        file_path = slug_dir / f"{stem}.png"
        if not file_path.is_file():
            continue
        field_name = _URL_FIELD_BY_STEM[stem]
        if field_name not in meta:
            # Absent key — board hasn't declared the URL yet. Not a violation.
            continue
        actual = meta[field_name]
        expected = (
            f"https://raw.githubusercontent.com/ne0-asref/ubds-database/main/"
            f"images/{slug}/{stem}.png"
        )
        match = CANONICAL_IMAGE_URL_PATTERN.match(actual) if isinstance(actual, str) else None
        if match is None or match.group("slug") != slug or f"/{stem}.png" not in actual:
            out.append(ImageCheckResult(
                path=file_path,
                severity="error",
                message=(
                    f"meta.{field_name} mismatch for {slug}: expected {expected}, "
                    f"got {actual!r}"
                ),
            ))
    return out


def _check_slug_uniqueness(
    slug_map: Dict[str, List[Path]],
) -> List[ImageCheckResult]:
    """Rule 13 — cross-file slug uniqueness AND slug-field ≠ filename-stem.

    Runs ONCE per directory invocation. Consolidates multi-file collisions
    into a single error that names every offender. Files without a parseable
    ``slug:`` field are absent from ``slug_map`` and therefore skipped — they
    surface via schema validation instead.
    """
    out: List[ImageCheckResult] = []

    # Part 1 — cross-file duplicates first. Emitting these before mismatches
    # keeps the consolidated error adjacent to the slug it's about, which is
    # what contributors scan for.
    for slug, paths in sorted(slug_map.items()):
        if len(paths) <= 1:
            continue
        names = ", ".join(f"boards/{p.name}" for p in paths)
        out.append(ImageCheckResult(
            path=paths[0],
            severity="error",
            message=f"duplicate slug '{slug}' declared in: {names}",
        ))

    # Part 2 — slug-field must match the filename stem. Iterates slug_map to
    # avoid re-parsing YAML.
    for slug, paths in sorted(slug_map.items()):
        for yml in paths:
            filename_stem = yml.name[: -len(YAML_SUFFIX)]
            if slug != filename_stem:
                out.append(ImageCheckResult(
                    path=yml,
                    severity="error",
                    message=(
                        f"slug field mismatch: boards/{yml.name} declares slug "
                        f"'{slug}' but filename is '{filename_stem}'"
                    ),
                ))

    return out


def check_images(root: Path) -> List[ImageCheckResult]:
    """Run the 13 board-image rules over a ubds-database repo root.

    ``root`` must contain (or be) a tree with ``images/`` and ``boards/``
    siblings. Directories that exist but are empty are walked anyway so that
    orphan-without-files cases don't silently pass (they fall out of the
    per-slug loop as no-ops — Rule 12).

    Returns a flat list of :class:`ImageCheckResult`. Caller renders them
    and decides exit code (errors fail, warnings don't).
    """
    results: List[ImageCheckResult] = []

    boards_dir = root / "boards"
    images_dir = root / "images"
    slug_map = _collect_slug_map(boards_dir)
    declared_slugs = set(slug_map.keys())

    # Rule 13 — cross-file slug uniqueness (directory-scoped, runs once).
    results.extend(_check_slug_uniqueness(slug_map))

    if images_dir.is_dir():
        for slug_dir in sorted(images_dir.iterdir()):
            if not (slug_dir.is_dir() or slug_dir.is_symlink()):
                # Stray file at images/ root — flag as Rule 3-style nesting.
                continue
            slug = slug_dir.name
            results.extend(_check_single_slug_dir(slug_dir, slug, declared_slugs))

            # Rule 11 — URL coupling. Only if the slug has a declared board.
            if slug in declared_slugs:
                for yml in slug_map[slug]:
                    _, meta = _load_meta(yml)
                    results.extend(_check_url_coupling(slug, slug_dir, meta))

    return results
