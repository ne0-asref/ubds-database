"""``dbf migrate`` — v1.1 → v1.2 in-place upgrades for board YAML files.

Applies three idempotent, line-preserving transformations:

1. Insert ``aliases: []`` after ``ubds_version:`` if the field is missing.
2. Insert ``manufacturer_slug: <slug>`` after ``manufacturer:`` if the
   field is missing AND :func:`vendor_map.slug_for_manufacturer` resolves
   to a known canonical slug (i.e. not the ``unknown`` fallback).
3. Bump ``ubds_version: '1.1'`` → ``'1.2'`` if the post-transform text
   contains any v1.2 marker (top-level ``aliases:`` /
   ``manufacturer_slug:`` or ``meta.confidence_skipped`` /
   ``meta.fetch_warnings`` / ``meta.source_quality``).

The optional :func:`nest_file` helper supports ``--nest-by-manufacturer``
by moving flat-layout boards into ``boards/<manufacturer-slug>/``.

**No ``yaml.dump`` round-trip — ever.** Comments + key ordering matter
to humans reviewing diffs; the C21 D21.6 carry-forward rule mandates
line-preserving string edits. Mirror :func:`validate._normalize_manufacturer_line`.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

from . import validate as _validate
from .vendor_map import UNKNOWN_MANUFACTURER_SLUG, slug_for_manufacturer


# ---------------------------------------------------------------------------
# Pure-text transforms
# ---------------------------------------------------------------------------


_UBDS_VERSION_RE = re.compile(
    r'^(?P<prefix>\s*ubds_version\s*:\s*)'
    r'(?:"(?P<dq>[^"]*)"|\'(?P<sq>[^\']*)\'|(?P<bare>\S+))'
    r'(?P<suffix>\s*(?:#.*)?)$'
)
_MANUFACTURER_RE = re.compile(
    r'^(?P<prefix>\s*manufacturer\s*:\s*)'
    r'(?:"(?P<dq>[^"]*)"|\'(?P<sq>[^\']*)\'|(?P<bare>[^#\n]+?))'
    r'(?P<suffix>\s*(?:#.*)?)$'
)
_ALIASES_TOP_LEVEL_RE = re.compile(r'^aliases\s*:', re.MULTILINE)
_MANUFACTURER_SLUG_TOP_LEVEL_RE = re.compile(r'^manufacturer_slug\s*:', re.MULTILINE)
_V12_MARKER_RE = re.compile(
    r'^(?:aliases|manufacturer_slug)\s*:'
    r'|^\s+(?:confidence_skipped|fetch_warnings|source_quality)\s*:',
    re.MULTILINE,
)


def detect_version(text: str) -> Optional[str]:
    """Return the literal ``ubds_version`` value, or ``None`` if absent."""
    for line in text.splitlines():
        m = _UBDS_VERSION_RE.match(line)
        if m:
            return m.group("dq") or m.group("sq") or m.group("bare")
    return None


def _read_manufacturer_value(text: str) -> Optional[str]:
    for line in text.splitlines():
        m = _MANUFACTURER_RE.match(line)
        if m:
            return (m.group("dq") or m.group("sq") or m.group("bare") or "").strip()
    return None


def _split_lines_keepends(text: str) -> List[str]:
    return text.splitlines(keepends=True)


def add_aliases(text: str) -> Tuple[str, bool]:
    """Insert ``aliases: []`` directly after the ``ubds_version:`` line.

    No-op if a top-level ``aliases:`` is already present. Returns
    ``(new_text, changed)``.
    """
    if _ALIASES_TOP_LEVEL_RE.search(text):
        return text, False
    lines = _split_lines_keepends(text)
    for i, line in enumerate(lines):
        if _UBDS_VERSION_RE.match(line.rstrip("\n")):
            ending = "\n" if line.endswith("\n") else "\n"
            lines.insert(i + 1, f"aliases: []{ending}")
            return "".join(lines), True
    # No ubds_version line — leave untouched (validate gate would have aborted).
    return text, False


def add_manufacturer_slug(text: str) -> Tuple[str, Optional[str]]:
    """Insert ``manufacturer_slug: <slug>`` after the ``manufacturer:`` line.

    No-op if a top-level ``manufacturer_slug:`` is already present, or if
    the manufacturer cannot be resolved to a known canonical slug. Returns
    ``(new_text, slug_added_or_None)``.
    """
    if _MANUFACTURER_SLUG_TOP_LEVEL_RE.search(text):
        return text, None
    mfr = _read_manufacturer_value(text)
    if not mfr:
        return text, None
    slug = slug_for_manufacturer(mfr)
    if slug == UNKNOWN_MANUFACTURER_SLUG:
        return text, None
    lines = _split_lines_keepends(text)
    for i, line in enumerate(lines):
        if _MANUFACTURER_RE.match(line.rstrip("\n")):
            ending = "\n" if line.endswith("\n") else "\n"
            lines.insert(i + 1, f"manufacturer_slug: {slug}{ending}")
            return "".join(lines), slug
    return text, None


def _has_v12_marker(text: str) -> bool:
    return _V12_MARKER_RE.search(text) is not None


def bump_version_if_v12(text: str) -> Tuple[str, bool]:
    """Bump ``ubds_version: '1.1'`` to ``'1.2'`` if any v1.2 field is present.

    Preserves the original quoting style (double-quoted, single-quoted, or
    bare). No-op if no v1.2 marker is present, or if the version is not
    exactly ``1.1``.
    """
    if not _has_v12_marker(text):
        return text, False
    lines = _split_lines_keepends(text)
    for i, line in enumerate(lines):
        body = line.rstrip("\n")
        m = _UBDS_VERSION_RE.match(body)
        if not m:
            continue
        current = m.group("dq") or m.group("sq") or m.group("bare")
        if current != "1.1":
            return text, False
        prefix = m.group("prefix")
        suffix = m.group("suffix") or ""
        if m.group("dq") is not None:
            new_value = '"1.2"'
        elif m.group("sq") is not None:
            new_value = "'1.2'"
        else:
            new_value = "1.2"
        ending = "\n" if line.endswith("\n") else ""
        lines[i] = f"{prefix}{new_value}{suffix}{ending}"
        return "".join(lines), True
    return text, False


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


_V10_SENTINEL_MSG = "v1.0 → v1.1 not implemented"


@dataclass
class MigrateReport:
    """One file's migration outcome.

    ``changes`` lists human-readable descriptions of what *would* change
    (dry-run) or *did* change (in-place). ``aborted`` flags pre-write
    schema-validation failure. ``skipped_reason`` is set for v1.0 inputs.
    ``written`` is True only when an in-place write touched disk.
    ``moved_to`` is set when ``--nest-by-manufacturer`` relocates the
    file. ``new_text`` carries the post-transform contents for dry-run
    rendering by the CLI layer.
    """

    file: Path
    changes: List[str] = field(default_factory=list)
    aborted: bool = False
    skipped_reason: Optional[str] = None
    written: bool = False
    moved_to: Optional[Path] = None
    new_text: Optional[str] = None


def migrate_text(text: str) -> Tuple[str, MigrateReport]:
    """Apply the three idempotent transforms to a YAML string.

    The returned :class:`MigrateReport` has ``file`` set to a placeholder
    (the caller must overwrite it). Use :func:`migrate_file` for the
    file-level wrapper.
    """
    report = MigrateReport(file=Path("<text>"))
    version = detect_version(text)
    if version == "1.0":
        report.skipped_reason = _V10_SENTINEL_MSG
        return text, report

    new_text, aliases_changed = add_aliases(text)
    if aliases_changed:
        report.changes.append("added aliases: []")

    new_text, slug_added = add_manufacturer_slug(new_text)
    if slug_added is not None:
        report.changes.append(f"added manufacturer_slug: {slug_added}")

    new_text, version_bumped = bump_version_if_v12(new_text)
    if version_bumped:
        report.changes.append("bumped ubds_version 1.1 -> 1.2")

    report.new_text = new_text
    return new_text, report


def migrate_file(path: Path, *, in_place: bool = False) -> MigrateReport:
    """Read ``path``, run pre-write validation, then apply migrations.

    On any pre-existing schema violation the migrate aborts WITHOUT
    writing — a half-bumped corrupt file is worse than no migrate.
    Default mode is dry-run; pass ``in_place=True`` to write.
    """
    original = path.read_text(encoding="utf-8")

    # Detect v1.0 BEFORE schema-validating: v1.0 files would fail the
    # bundled v1.x schema for unrelated reasons (different shape), and
    # the spec asks for a friendly "not implemented" sentinel rather than
    # a generic abort. Same for any version we don't know how to migrate.
    if detect_version(original) == "1.0":
        report = MigrateReport(file=path, skipped_reason=_V10_SENTINEL_MSG)
        return report

    pre = _validate.validate_file(path)
    # Aborted iff the original file fails validation OUTRIGHT (errors or
    # parse failure or major-version error). A version-warn (e.g. file is
    # already v1.2 vs CLI's bundled v1.1) is fine — we still want migrate
    # to be a no-op on a clean v1.2 file.
    if pre.parse_error is not None or pre.errors or pre.version_level == "error":
        report = MigrateReport(file=path, aborted=True)
        return report

    new_text, report = migrate_text(original)
    report.file = path

    if in_place and new_text != original and report.skipped_reason is None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(new_text, encoding="utf-8")
        os.replace(tmp, path)
        report.written = True

    return report


# ---------------------------------------------------------------------------
# --nest-by-manufacturer
# ---------------------------------------------------------------------------


def _is_flat(path: Path, boards_root: Path) -> bool:
    try:
        rel = path.resolve().relative_to(boards_root.resolve())
    except (OSError, ValueError):
        return False
    return len(rel.parts) == 1


def nest_file(
    path: Path,
    boards_root: Path,
    *,
    in_place: bool = False,
) -> Optional[Path]:
    """Compute (and optionally execute) the move from flat to nested layout.

    Returns the destination ``Path`` when a move would happen, or ``None``
    when the file is already nested / outside ``boards_root`` / lacks a
    parseable ``manufacturer:``. With ``in_place=True`` the move actually
    executes.
    """
    if not _is_flat(path, boards_root):
        return None
    text = path.read_text(encoding="utf-8")
    mfr = _read_manufacturer_value(text)
    if mfr is None:
        return None
    slug = slug_for_manufacturer(mfr)  # may be UNKNOWN_MANUFACTURER_SLUG
    dest = boards_root / slug / path.name
    if in_place:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(dest))
    return dest
