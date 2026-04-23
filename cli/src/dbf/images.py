"""``dbf add-image`` core — atomic image copy + line-preserving YAML URL write.

Given a board slug, a local PNG path, and a canonical view (``top-view``,
``pinout``, ``angle``, ``bottom-view``, ``block-diagram``), this module
copies the source file to ``images/<slug>/<view>.png`` AND rewrites the
URL field inside the board's ``meta:`` block in the matching
``boards/<slug>.ubds.yaml``. Both writes are atomic (staged to a sibling
``.tmp`` then ``os.replace``-d). A ``.bak`` is dropped next to the YAML
on first edit (same convention as ``apply_fixes`` in ``validate.py``).

The YAML edit is line-preserving (decision D21.6): existing comments,
blank lines, and key ordering survive untouched. We never
``yaml.dump``-round-trip, because that destroys editorial comments that
some boards carry.

Pre-write schema validation is MANDATORY. We parse the proposed edited
text via the same UBDS schema ``validate_file`` uses and abort BEFORE any
filesystem mutation if the edit would break validation. This keeps the
"fail fast, leave nothing half-written" promise.

Public surface::

    add_image(
        *,
        slug: str,
        source_path: Path,
        as_view: str,
        repo_root: Path,
        write_yaml: bool = True,
        overwrite: bool = False,
    ) -> AddImageResult

Raises ``AddImageError`` (single exception type) for every user-facing
failure with a precomposed, actionable message.
"""
from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml
from jsonschema import Draft7Validator, FormatChecker

from .constants import (
    CANONICAL_IMAGE_FILENAMES,
    MAX_IMAGE_BYTES,
    PNG_SIGNATURE,
)
from .schema import load_schema

__all__ = [
    "AddImageError",
    "AddImageResult",
    "YamlEdit",
    "add_image",
    "canonical_image_url",
]

_URL_BASE = "https://raw.githubusercontent.com/ne0-asref/ubds-database/main/images"

# Views that populate the primary image slot (meta.image_url) versus
# the dedicated pinout slot.
_PINOUT_VIEW = "pinout"

# Slug must be lowercased alphanumerics + hyphens. This is deliberately
# stricter than a simple lowercase check so that a slug like "../foo"
# cannot walk us out of repo_root when we resolve boards/<slug>.ubds.yaml
# or write into images/<slug>/.
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------

@dataclass
class YamlEdit:
    path: Path
    line_number: int  # 1-indexed
    old: str
    new: str


@dataclass
class AddImageResult:
    slug: str
    source: Path
    dest: Path
    yaml_edit: Optional[YamlEdit]
    backup: Optional[Path]


class AddImageError(Exception):
    """User-facing error raised by :func:`add_image`."""


# ---------------------------------------------------------------------------
# URL derivation
# ---------------------------------------------------------------------------

def canonical_image_url(slug: str, as_view: str) -> str:
    return f"{_URL_BASE}/{slug}/{as_view}.png"


def _target_yaml_key(as_view: str) -> str:
    return "pinout_image_url" if as_view == _PINOUT_VIEW else "image_url"


# ---------------------------------------------------------------------------
# Source + dest preflight
# ---------------------------------------------------------------------------

def _check_source(source_path: Path) -> None:
    if not source_path.exists():
        raise AddImageError(f"source file not found: {source_path}")
    if not source_path.is_file():
        raise AddImageError(f"source is not a regular file: {source_path}")
    try:
        head = source_path.read_bytes()[:8]
    except OSError as exc:
        raise AddImageError(f"could not read source file {source_path}: {exc}") from exc
    if head[: len(PNG_SIGNATURE)] != PNG_SIGNATURE:
        raise AddImageError(
            f"{source_path} is not a PNG (missing 8-byte PNG signature). "
            f"`dbf add-image` accepts PNG only."
        )
    size = source_path.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise AddImageError(
            f"{source_path} is {size} bytes; max allowed size is "
            f"{MAX_IMAGE_BYTES} bytes (1 MB). Shrink the PNG before retrying."
        )


def _resolve_board_yaml(slug: str, repo_root: Path) -> Path:
    boards_dir = repo_root / "boards"
    candidate = boards_dir / f"{slug}.ubds.yaml"
    if candidate.is_file():
        return candidate
    known: List[str] = []
    if boards_dir.is_dir():
        for p in boards_dir.glob("*.ubds.yaml"):
            known.append(p.name[: -len(".ubds.yaml")])
    suggestions = difflib.get_close_matches(slug, known, n=3, cutoff=0.6)
    if suggestions:
        joined = ", ".join(suggestions)
        raise AddImageError(
            f"no board '{slug}'; did you mean: {joined}?"
        )
    raise AddImageError(f"no board '{slug}' in {boards_dir}")


# ---------------------------------------------------------------------------
# Line-preserving YAML edit
# ---------------------------------------------------------------------------

_META_BLOCK_LINE = re.compile(r"^(?P<indent>\s*)meta\s*:\s*(?:#.*)?$")
_ANY_META_LINE = re.compile(r"^\s*meta\s*:")


def _split_lines_keepends(text: str) -> List[str]:
    return text.splitlines(keepends=True)


def _indent_of(body: str) -> int:
    return len(body) - len(body.lstrip(" "))


def _locate_meta_block(lines: List[str]) -> tuple[int, int, int]:
    """Find the line index of the ``meta:`` block and its inclusive range.

    Returns ``(meta_idx, end_idx, child_indent)`` where:
    - ``meta_idx`` — 0-indexed line of the ``meta:`` anchor.
    - ``end_idx`` — exclusive end-of-block line index (first line whose
      indent is ``<= meta_indent`` after ``meta_idx``, or ``len(lines)``).
    - ``child_indent`` — indent of meta's block-style children; inferred
      from the first indented child, or ``meta_indent + 2`` if empty.

    Raises ``AddImageError`` if the block is missing or flow-style.
    """
    meta_idx: Optional[int] = None
    meta_indent = 0
    for i, raw in enumerate(lines):
        body = raw.rstrip("\n").rstrip("\r")
        m = _META_BLOCK_LINE.match(body)
        if m:
            meta_idx = i
            meta_indent = len(m.group("indent"))
            break
    if meta_idx is None:
        for raw in lines:
            if _ANY_META_LINE.match(raw):
                raise AddImageError(
                    "board YAML's `meta:` key is flow-style (e.g. `meta: {}`); "
                    "rewrite it as a block-style mapping with indented children "
                    "before running `dbf add-image`."
                )
        raise AddImageError(
            "board YAML is missing `meta:` block (required by UBDS schema — "
            "add one manually before running `dbf add-image`)."
        )

    child_indent = meta_indent + 2
    first_child_seen = False
    end_idx = len(lines)
    for i in range(meta_idx + 1, len(lines)):
        body = lines[i].rstrip("\n").rstrip("\r")
        if not body.strip():
            continue  # blank line — stays inside block
        ind = _indent_of(body)
        if ind <= meta_indent:
            end_idx = i
            break
        if not first_child_seen:
            child_indent = ind
            first_child_seen = True
    return meta_idx, end_idx, child_indent


def _find_key_line(
    lines: List[str], start: int, end: int, indent: int, key: str
) -> Optional[int]:
    """Return the line index of ``<indent><key>:`` inside ``[start, end)``."""
    prefix = " " * indent + key
    for i in range(start, end):
        body = lines[i].rstrip("\n").rstrip("\r")
        if not body.startswith(prefix):
            continue
        rest = body[len(prefix):]
        # rest must start with zero-or-more spaces followed by ':'
        stripped = rest.lstrip(" ")
        if stripped.startswith(":"):
            # Also enforce exact indent (no leading additional spaces).
            actual_indent = _indent_of(body)
            if actual_indent == indent:
                return i
    return None


def _preserve_line_ending(original: str, new_body: str) -> str:
    if original.endswith("\r\n"):
        return new_body + "\r\n"
    if original.endswith("\n"):
        return new_body + "\n"
    return new_body


def _compute_yaml_edit(
    yaml_path: Path, yaml_text: str, target_key: str, new_url: str
) -> tuple[str, YamlEdit]:
    """Return ``(edited_text, YamlEdit)`` for a line-preserving URL write.

    Raises ``AddImageError`` on meta-block problems.
    """
    lines = _split_lines_keepends(yaml_text)
    meta_idx, end_idx, child_indent = _locate_meta_block(lines)
    existing_idx = _find_key_line(lines, meta_idx + 1, end_idx, child_indent, target_key)

    new_line_body = f'{" " * child_indent}{target_key}: "{new_url}"'

    if existing_idx is not None:
        old_line = lines[existing_idx]
        new_line = _preserve_line_ending(old_line, new_line_body)
        lines[existing_idx] = new_line
        edit = YamlEdit(
            path=yaml_path,
            line_number=existing_idx + 1,
            old=old_line.rstrip("\n").rstrip("\r"),
            new=new_line.rstrip("\n").rstrip("\r"),
        )
        return "".join(lines), edit

    # Insert right after the last non-blank child (or right after `meta:` if empty).
    insert_at = meta_idx + 1
    for i in range(meta_idx + 1, end_idx):
        if lines[i].strip():
            insert_at = i + 1

    # Ensure line above has a newline terminator so the new line doesn't glue onto it.
    if insert_at > 0 and lines and not lines[insert_at - 1].endswith(("\n", "\r\n")):
        lines[insert_at - 1] = lines[insert_at - 1] + "\n"

    new_line = new_line_body + "\n"
    lines.insert(insert_at, new_line)
    edit = YamlEdit(
        path=yaml_path,
        line_number=insert_at + 1,
        old="",
        new=new_line_body,
    )
    return "".join(lines), edit


# ---------------------------------------------------------------------------
# Pre-write schema validation (no-write; in-memory)
# ---------------------------------------------------------------------------

_validator: Optional[Draft7Validator] = None


def _get_validator() -> Draft7Validator:
    global _validator
    if _validator is None:
        _validator = Draft7Validator(load_schema(), format_checker=FormatChecker())
    return _validator


def _validate_in_memory(yaml_text: str) -> List[str]:
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        return [f"YAML parse error after edit: {exc}"]
    if not isinstance(data, dict):
        return ["top-level YAML value is not a mapping after edit"]
    errs = []
    for e in _get_validator().iter_errors(data):
        path = ".".join(str(x) for x in e.absolute_path) or "<root>"
        errs.append(f"{path}: {e.message}")
    return errs


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------

def _atomic_write_bytes(dest: Path, data: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def _atomic_write_text(dest: Path, text: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def add_image(
    *,
    slug: str,
    source_path: Path,
    as_view: str,
    repo_root: Path,
    write_yaml: bool = True,
    overwrite: bool = False,
) -> AddImageResult:
    """Copy ``source_path`` to ``images/<slug>/<as_view>.png`` atomically.

    When ``write_yaml`` is true (default), also rewrite the canonical URL in
    the board's ``meta:`` block (line-preserving, with a one-shot ``.bak``).
    Every precondition is checked before any filesystem mutation so a
    rejected invocation leaves the tree unchanged.
    """
    # 1. slug must be lowercase BEFORE any filesystem probe. A mixed-case
    # slug would otherwise fall through to the nearest-match branch with a
    # misleading "no board" message.
    if slug != slug.lower():
        raise AddImageError(
            f"slug must be lowercase (got '{slug}'). UBDS slugs are "
            "lowercased [a-z0-9-]. Rename the board file first."
        )
    # Block path-escape characters (dot, slash, backslash, null, etc.)
    # before any filesystem path is constructed from ``slug``.
    if not _SLUG_PATTERN.match(slug):
        raise AddImageError(
            f"invalid slug '{slug}': must match [a-z0-9][a-z0-9-]* "
            "(lowercased alphanumerics and hyphens only)."
        )

    # 2. view must be canonical
    if as_view not in CANONICAL_IMAGE_FILENAMES:
        options = ", ".join(CANONICAL_IMAGE_FILENAMES)
        raise AddImageError(
            f"unknown view '{as_view}'. Canonical options: {options}."
        )

    # 3. slug → board YAML (nearest-match suggestions on miss)
    yaml_path = _resolve_board_yaml(slug, repo_root)

    # 4. source preflight
    source_path = Path(source_path)
    _check_source(source_path)

    # 5. dest existence
    dest = repo_root / "images" / slug / f"{as_view}.png"
    if dest.exists() and not overwrite:
        raise AddImageError(
            f"{dest} already exists. Pass --overwrite to replace it."
        )

    # 6. pre-write YAML edit + schema validation (no writes yet)
    yaml_edit_preview: Optional[YamlEdit] = None
    edited_yaml_text: Optional[str] = None
    original_yaml_text: Optional[str] = None
    if write_yaml:
        original_yaml_text = yaml_path.read_text(encoding="utf-8")
        target_key = _target_yaml_key(as_view)
        new_url = canonical_image_url(slug, as_view)
        edited_yaml_text, yaml_edit_preview = _compute_yaml_edit(
            yaml_path, original_yaml_text, target_key, new_url
        )
        schema_errs = _validate_in_memory(edited_yaml_text)
        if schema_errs:
            joined = "\n  - ".join(schema_errs)
            raise AddImageError(
                f"refusing to write {yaml_path}: proposed edit would make it "
                f"fail UBDS schema validation:\n  - {joined}"
            )

    # 7. atomic image copy
    src_bytes = source_path.read_bytes()
    _atomic_write_bytes(dest, src_bytes)

    # 8. atomic YAML write + .bak
    backup: Optional[Path] = None
    yaml_edit: Optional[YamlEdit] = None
    if write_yaml and edited_yaml_text is not None and original_yaml_text is not None:
        bak = yaml_path.with_suffix(yaml_path.suffix + ".bak")
        if not bak.exists():
            bak.write_text(original_yaml_text, encoding="utf-8")
        backup = bak
        _atomic_write_text(yaml_path, edited_yaml_text)
        yaml_edit = yaml_edit_preview

    return AddImageResult(
        slug=slug,
        source=source_path,
        dest=dest,
        yaml_edit=yaml_edit,
        backup=backup,
    )
