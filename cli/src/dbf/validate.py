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
import unicodedata as _ud
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
from .schema import load_manufacturer_schema, load_schema
from .vendor_map import normalize_vendor
from .version import check_version

# ---------------------------------------------------------------------------
# Path collection
# ---------------------------------------------------------------------------

YAML_SUFFIX = ".ubds.yaml"

FLAT_LAYOUT_DEPRECATION = (
    "flat layout deprecated; move boards under "
    "boards/<manufacturer-slug>/<slug>.ubds.yaml"
)


def collect_paths(arg: str) -> List[Path]:
    """Expand ``arg`` (file, directory, or glob) into a sorted list of YAML files.

    - File: returned as-is (must end in ``.ubds.yaml`` to be considered).
    - Directory: walked recursively for ``*.ubds.yaml``. Both the legacy
      flat layout (``boards/<slug>.ubds.yaml``) and the C22 U2 nested
      layout (``boards/<manufacturer-slug>/<slug>.ubds.yaml``) are
      accepted during the transition window — the validator emits a
      deprecation warning for any file still at the flat-layout depth.
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


def is_flat_layout_board(path: Path, boards_root: Path) -> bool:
    """True iff ``path`` is a ``*.ubds.yaml`` sitting directly under
    ``boards_root`` (legacy layout — flagged for deprecation).

    Returns False for files outside ``boards_root`` (e.g. fixture YAMLs in
    test temp dirs, single-file invocations on standalone YAMLs) so the
    deprecation warning never fires outside the canonical tree.
    """
    try:
        resolved_path = path.resolve()
        resolved_root = boards_root.resolve()
    except OSError:
        return False
    try:
        rel = resolved_path.relative_to(resolved_root)
    except ValueError:
        return False
    # rel.parts == ("<slug>.ubds.yaml",) means the file is directly under
    # boards/, i.e. flat layout. Anything deeper (("<mfr>", "<slug>.yaml"))
    # is the new nested layout and stays silent.
    return len(rel.parts) == 1


def find_flat_layout_files(arg: str, paths: List[Path]) -> List[Path]:
    """Return the subset of ``paths`` that are flat-layout entries under
    ``<arg>/boards/`` or ``<arg>`` (when the caller passed boards/ directly).

    Used by the CLI to render the one-time deprecation warning per
    ``dbf validate`` invocation. Files outside the boards tree (single-file
    invocations on a temporary fixture, ad-hoc trees) never trigger.
    """
    arg_path = Path(arg)
    if arg_path.is_file():
        return []
    if arg_path.is_dir():
        if arg_path.name == "boards":
            boards_root = arg_path
        elif (arg_path / "boards").is_dir():
            boards_root = arg_path / "boards"
        else:
            # Caller passed an ad-hoc directory (no boards/ child); nothing
            # in it counts as "flat layout" for deprecation purposes.
            return []
    else:
        return []
    return [p for p in paths if is_flat_layout_board(p, boards_root)]


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

    errors = list(_get_validator().iter_errors(data))
    errors.extend(_check_confidence_mutual_exclusion(data))
    errors.sort(key=lambda e: list(e.absolute_path))
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


def _check_confidence_mutual_exclusion(data: dict) -> List[ValidationError]:
    """C22 U5 — ``meta.confidence_skipped`` and ``meta.confidence`` keys must
    not overlap.

    A section listed in ``confidence_skipped`` is hidden from the UI outright;
    a section keyed in ``confidence`` carries a verification level. Documenting
    both for the same section is contradictory — the contributor must pick one.
    Emits one :class:`ValidationError` per offending section so the renderer
    can show one clear block per problem.

    Schema (U1) accepts each side in isolation; this function only fires when
    both shapes are well-formed (dict + list-of-strings). Malformed shapes
    surface via schema validation instead.
    """
    meta = data.get("meta")
    if not isinstance(meta, dict):
        return []
    confidence = meta.get("confidence")
    skipped = meta.get("confidence_skipped")
    if not isinstance(confidence, dict) or not isinstance(skipped, list):
        return []

    out: List[ValidationError] = []
    confidence_keys = set(confidence.keys())
    seen: set = set()
    for idx, section in enumerate(skipped):
        if not isinstance(section, str) or section in seen:
            continue
        seen.add(section)
        if section in confidence_keys:
            err = ValidationError(
                message=(
                    f"section {section!r} is in meta.confidence_skipped "
                    f"AND has a meta.confidence value — pick one."
                ),
                validator="confidence_mutual_exclusion",
                validator_value=section,
                instance=section,
                path=("meta", "confidence_skipped", idx),
            )
            out.append(err)
    return out


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

    Walks ``boards_dir`` recursively so both the legacy flat layout and the
    C22 U2 nested ``boards/<manufacturer-slug>/<board-slug>.ubds.yaml``
    layout are covered in one pass. Only files whose content is a mapping
    with a scalar ``slug`` key are included. Parse failures are silently
    skipped here — the schema-level validator surfaces them separately.
    """
    out: Dict[str, List[Path]] = {}
    if not boards_dir.is_dir():
        return out
    for yml in sorted(boards_dir.rglob(f"*{YAML_SUFFIX}")):
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


# ---------------------------------------------------------------------------
# Alias-collision validation (C22 U4)
#
# ``check_aliases(root)`` walks every board YAML under ``root/boards/`` and
# every ``root/manufacturers/<slug>.yaml``. It builds a registry of:
#
#   - board ``slug``                (kind=slug)
#   - board ``aliases[]`` entries   (kind=alias)
#   - manufacturer ``slug``         (kind=manufacturer-slug)
#   - manufacturer ``canonical_name`` (kind=manufacturer-canonical-name)
#
# keyed by a normalized form (NFKC + casefold + whitespace-stripped).
# Two distinct sources whose normalized values collide are reported as one
# :class:`AliasCollision`, *provided* at least one of them is alias-valued
# (``alias`` or ``manufacturer-canonical-name``). Pure slug-vs-slug
# collisions are intentionally NOT this rule's job — image-validator Rule 13
# already catches duplicate board slugs and a future check will catch
# duplicate manufacturer slugs.
# ---------------------------------------------------------------------------

_ALIAS_WHITESPACE_RE = re.compile(r"\s+")

# Source kinds that COUNT as alias-equivalents for collision triggering.
# A collision must include at least one of these; otherwise it falls through
# to other validators (Rule 13 for board slugs, etc.).
_ALIAS_LIKE_KINDS = frozenset({
    "alias",
    "manufacturer-canonical-name",
    "manufacturer-alias",
})


def _normalize_alias(value: str) -> str:
    """Return the comparison key for ``value``.

    Case-folded (so casing differs are equal) and with all whitespace stripped
    (so ``"RPi 5"`` and ``"rpi5"`` are equal). NFKC first so visually-identical
    Unicode forms compare equal too.
    """
    if not isinstance(value, str):
        return ""
    s = _ud.normalize("NFKC", value)
    s = s.casefold()
    return _ALIAS_WHITESPACE_RE.sub("", s)


@dataclass
class AliasCollision:
    """One within-batch alias collision.

    ``paths`` lists every distinct file involved (deduplicated, sorted by
    path string). ``sources`` is the human-readable rendering used in the
    error message — one entry per (file, kind, raw_value) triple, in the
    order they were collected.
    """

    paths: List[Path]
    sources: List[str]
    normalized: str
    severity: ImageSeverity = "error"

    @property
    def message(self) -> str:
        return (
            f"alias collision (normalized={self.normalized!r}): "
            + "; ".join(self.sources)
        )


def _iter_yaml_files(directory: Path, suffix: str) -> List[Path]:
    """Sorted list of ``*<suffix>`` files under ``directory`` (recursive).

    Manufacturer files use ``.yaml`` (not ``.ubds.yaml``); board files use
    ``.ubds.yaml`` and may live one level deep under
    ``boards/<manufacturer-slug>/`` after U2's nesting migration.
    """
    if not directory.is_dir():
        return []
    return sorted(directory.rglob(f"*{suffix}"))


def check_aliases(root: Path) -> List[AliasCollision]:
    """Within-batch alias-collision check across boards/ and manufacturers/.

    See module-level docstring for the registry kinds + collision rules.
    Returns one :class:`AliasCollision` per colliding normalized key, sorted
    by that key for deterministic output. Empty list when clean.
    """
    boards_dir = root / "boards"
    manufacturers_dir = root / "manufacturers"

    pool: Dict[str, List[Tuple[Path, str, str]]] = {}

    def _add(value: object, path: Path, kind: str) -> None:
        if not isinstance(value, str) or not value:
            return
        key = _normalize_alias(value)
        if not key:
            return
        pool.setdefault(key, []).append((path, kind, value))

    for yml in _iter_yaml_files(boards_dir, YAML_SUFFIX):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        _add(data.get("slug"), yml, "slug")
        aliases = data.get("aliases")
        if isinstance(aliases, list):
            for alias in aliases:
                _add(alias, yml, "alias")

    for yml in _iter_yaml_files(manufacturers_dir, ".yaml"):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        _add(data.get("slug"), yml, "manufacturer-slug")
        _add(data.get("canonical_name"), yml, "manufacturer-canonical-name")
        mfr_aliases = data.get("aliases")
        if isinstance(mfr_aliases, list):
            for alias in mfr_aliases:
                _add(alias, yml, "manufacturer-alias")

    out: List[AliasCollision] = []
    for key, entries in sorted(pool.items()):
        # Collisions are cross-file only — a manufacturer file whose slug
        # equals its own canonical_name normalizes to the same key but is
        # NOT a collision (same record talking about itself).
        unique_paths = sorted({p for p, _, _ in entries}, key=str)
        if len(unique_paths) < 2:
            continue
        if not any(kind in _ALIAS_LIKE_KINDS for _, kind, _ in entries):
            continue
        descriptors = [
            f"{p}: {kind} {raw!r}" for p, kind, raw in entries
        ]
        out.append(AliasCollision(
            paths=unique_paths,
            sources=descriptors,
            normalized=key,
        ))
    return out


# ---------------------------------------------------------------------------
# Manufacturer index validation (C22 U3)
#
# ``validate_manufacturers(root)`` schema-checks every ``manufacturers/<slug>
# .yaml`` against ``ubds-manufacturer.schema.json`` AND enforces three
# directory-scoped rules:
#
#   1. ``slug`` field equals filename stem.
#   2. Add-criterion: a manufacturer file with no referencing board AND
#      ``well_known: true`` not set is rejected. The 14 well-known vendors
#      from the C22 spec-revision handoff §6 carry ``well_known: true`` in
#      their seed YAML; subsequent contributions must add the field
#      explicitly OR ship a board that references the manufacturer.
#   3. Manufacturer slug uniqueness across the directory.
#
# Cross-file alias-collision (rule from spec.md §Tests) is NOT this function's
# job — :func:`check_aliases` already covers it (with the U3 extension that
# pulls manufacturer ``aliases[]`` into the collision pool).
#
# ``check_manufacturer_links(root)`` enforces the board↔manufacturer index
# link rule:
#
#   When a board declares ``manufacturer_slug: <s>``, the file
#   ``manufacturers/<s>.yaml`` MUST exist AND the board's ``manufacturer:``
#   field MUST equal that file's ``canonical_name`` or be in its ``aliases``.
#
# Both functions are pure — they read disk and return a list. The CLI layer
# in ``cli.py`` formats and exits.
# ---------------------------------------------------------------------------

_MANUFACTURER_SUFFIX = ".yaml"


@dataclass
class ManufacturerError:
    """One violation found by :func:`validate_manufacturers`.

    ``severity`` mirrors :class:`ImageCheckResult` so the CLI can render
    errors and warnings uniformly. The U3 ruleset only emits errors today.
    """

    path: Path
    message: str
    severity: ImageSeverity = "error"


_manufacturer_validator: Optional[Draft7Validator] = None


def _get_manufacturer_validator() -> Draft7Validator:
    global _manufacturer_validator
    if _manufacturer_validator is None:
        _manufacturer_validator = Draft7Validator(
            load_manufacturer_schema(), format_checker=FormatChecker()
        )
    return _manufacturer_validator


def _collect_board_manufacturers(boards_dir: Path) -> List[dict]:
    """Return a list of ``{path, slug, manufacturer, manufacturer_slug}`` dicts.

    Used by both the manufacturer-orphan check and the link-rule check.
    Skips parse failures silently — schema validation surfaces them.
    """
    out: List[dict] = []
    if not boards_dir.is_dir():
        return out
    for yml in sorted(boards_dir.rglob(f"*{YAML_SUFFIX}")):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        out.append({
            "path": yml,
            "slug": data.get("slug"),
            "manufacturer": data.get("manufacturer"),
            "manufacturer_slug": data.get("manufacturer_slug"),
        })
    return out


def _load_manufacturer_yaml(path: Path) -> Optional[dict]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def validate_manufacturers(root: Path) -> List[ManufacturerError]:
    """Validate every ``manufacturers/<slug>.yaml`` under ``root``.

    Per-file rules:

    - Schema: file conforms to ``ubds-manufacturer.schema.json``.
    - Filename: ``slug`` field equals the filename stem.
    - Slug pattern: covered by schema (``^[a-z0-9]+(-[a-z0-9]+)*$``).
    - Parse: YAML must load to a top-level mapping.

    Directory-scoped rules:

    - Slug uniqueness across all manufacturer files.
    - Add-criterion: each manufacturer must either have ``well_known: true``
      OR at least one board referencing it (board's ``manufacturer:`` matches
      ``canonical_name`` / one of ``aliases``, OR board's ``manufacturer_slug``
      equals the manufacturer's slug).
    """
    out: List[ManufacturerError] = []
    manufacturers_dir = root / "manufacturers"
    if not manufacturers_dir.is_dir():
        return out

    files = _iter_yaml_files(manufacturers_dir, _MANUFACTURER_SUFFIX)
    if not files:
        return out

    schema_validator = _get_manufacturer_validator()
    seen_slugs: Dict[str, Path] = {}

    parsed: List[Tuple[Path, dict]] = []
    for yml in files:
        data = _load_manufacturer_yaml(yml)
        if data is None:
            out.append(ManufacturerError(
                path=yml,
                message=(
                    f"manufacturer file is not a valid YAML mapping: {yml}"
                ),
            ))
            continue
        # Schema validation.
        for err in sorted(
            schema_validator.iter_errors(data),
            key=lambda e: list(e.absolute_path),
        ):
            field = ".".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(ManufacturerError(
                path=yml,
                message=f"schema violation at {field}: {err.message}",
            ))
        # Filename-stem ↔ slug field.
        stem = yml.stem
        slug = data.get("slug")
        if isinstance(slug, str) and slug != stem:
            out.append(ManufacturerError(
                path=yml,
                message=(
                    f"slug field mismatch: file '{yml.name}' declares "
                    f"slug '{slug}' but stem is '{stem}'"
                ),
            ))
        # Slug uniqueness (only consider well-formed string slugs).
        if isinstance(slug, str) and slug:
            prior = seen_slugs.get(slug)
            if prior is not None:
                out.append(ManufacturerError(
                    path=yml,
                    message=(
                        f"duplicate manufacturer slug '{slug}': declared in "
                        f"{prior} and {yml}"
                    ),
                ))
            else:
                seen_slugs[slug] = yml
        parsed.append((yml, data))

    # Add-criterion: every manufacturer needs a referencing board OR
    # well_known: true. Collect referenced manufacturers from boards/.
    boards = _collect_board_manufacturers(root / "boards")

    referenced_slugs: set = set()
    referenced_names: set = set()  # normalized
    for b in boards:
        ms = b.get("manufacturer_slug")
        if isinstance(ms, str) and ms:
            referenced_slugs.add(ms)
        m = b.get("manufacturer")
        if isinstance(m, str) and m:
            referenced_names.add(_normalize_alias(m))

    for yml, data in parsed:
        if data.get("well_known") is True:
            continue
        slug = data.get("slug")
        canonical = data.get("canonical_name")
        aliases = data.get("aliases") or []
        candidates = {canonical}
        if isinstance(aliases, list):
            candidates.update(a for a in aliases if isinstance(a, str))
        normalized = {
            _normalize_alias(c) for c in candidates if isinstance(c, str) and c
        }
        slug_match = isinstance(slug, str) and slug in referenced_slugs
        name_match = bool(normalized & referenced_names)
        if not slug_match and not name_match:
            out.append(ManufacturerError(
                path=yml,
                message=(
                    f"orphan manufacturer: no board in boards/ references "
                    f"{yml.name} (set 'well_known: true' to grandfather, "
                    f"or add a board whose manufacturer matches "
                    f"canonical_name/aliases)"
                ),
            ))

    return out


@dataclass
class ManufacturerLinkError:
    """One board↔manufacturer index link violation."""

    board_path: Path
    message: str
    severity: ImageSeverity = "error"


def check_manufacturer_links(root: Path) -> List[ManufacturerLinkError]:
    """For every board with ``manufacturer_slug:``, verify the link.

    Rules:

    - The file ``manufacturers/<manufacturer_slug>.yaml`` must exist.
    - The board's ``manufacturer:`` must equal the manufacturer's
      ``canonical_name`` or appear in its ``aliases`` (compared
      case-insensitively + whitespace-collapsed via :func:`_normalize_alias`).

    Boards without a ``manufacturer_slug:`` field are silently ignored —
    the field is optional during the v1.1 → v1.2 transition window.
    """
    out: List[ManufacturerLinkError] = []
    manufacturers_dir = root / "manufacturers"
    boards_dir = root / "boards"
    if not boards_dir.is_dir():
        return out

    # Pre-load all manufacturer files keyed by slug for O(1) lookup.
    mfr_by_slug: Dict[str, dict] = {}
    for yml in _iter_yaml_files(manufacturers_dir, _MANUFACTURER_SUFFIX):
        data = _load_manufacturer_yaml(yml)
        if data is None:
            continue
        slug = data.get("slug")
        if isinstance(slug, str) and slug:
            mfr_by_slug[slug] = {"path": yml, "data": data}

    for b in _collect_board_manufacturers(boards_dir):
        mslug = b.get("manufacturer_slug")
        if not isinstance(mslug, str) or not mslug:
            continue
        entry = mfr_by_slug.get(mslug)
        if entry is None:
            out.append(ManufacturerLinkError(
                board_path=b["path"],
                message=(
                    f"manufacturer_slug '{mslug}' has no matching "
                    f"manufacturers/{mslug}.yaml"
                ),
            ))
            continue
        mfr = entry["data"]
        canonical = mfr.get("canonical_name")
        aliases = mfr.get("aliases") or []
        names: List[str] = []
        if isinstance(canonical, str) and canonical:
            names.append(canonical)
        if isinstance(aliases, list):
            names.extend(a for a in aliases if isinstance(a, str))
        manufacturer = b.get("manufacturer")
        if not isinstance(manufacturer, str) or not manufacturer:
            out.append(ManufacturerLinkError(
                board_path=b["path"],
                message=(
                    f"board declares manufacturer_slug '{mslug}' but is "
                    f"missing the manufacturer field"
                ),
            ))
            continue
        target = _normalize_alias(manufacturer)
        if target not in {_normalize_alias(n) for n in names}:
            allowed = ", ".join([repr(canonical)] + [repr(a) for a in aliases])
            out.append(ManufacturerLinkError(
                board_path=b["path"],
                message=(
                    f"board manufacturer {manufacturer!r} does not match "
                    f"manufacturers/{mslug}.yaml canonical_name or aliases "
                    f"({allowed})"
                ),
            ))

    return out
