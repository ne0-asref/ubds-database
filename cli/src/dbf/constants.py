"""Canonical image vocabulary — single Python source of truth.

Every consumer that needs to know the list of board-image filenames, the
URL shape, the max byte size, or the PNG-signature / RGBA constants
imports from this module. The same vocabulary is also declared in
``spec/ubds-v1.schema.json`` under ``meta.image_filenames`` (as an
informational enum) and referenced in ``CONTRIBUTING.md`` + the minimal
YAML template. ``cli/tests/test_canonical_vocab.py`` enforces that the
three sources never drift.

If you change anything here, expect the drift test to fail loudly — that
is the contract. Update the schema enum and docs in the same commit (or
the same PR) rather than silencing the test.
"""
import re


CANONICAL_IMAGE_FILENAMES: tuple[str, ...] = (
    "top-view",
    "pinout",
    "angle",
    "bottom-view",
    "block-diagram",
)

IMAGE_FALLBACKS: tuple[str, ...] = (
    "angle",
    "bottom-view",
    "block-diagram",
)

MAX_IMAGE_BYTES: int = 1_048_576

CANONICAL_IMAGE_URL_PATTERN: re.Pattern[str] = re.compile(
    r"^https://raw\.githubusercontent\.com/ne0-asref/ubds-database/main/images/"
    r"(?P<slug>[a-z0-9][a-z0-9-]*)/(top-view|pinout)\.png$"
)

PNG_SIGNATURE: bytes = b"\x89PNG\r\n\x1a\n"

PNG_IHDR_COLOR_TYPE_RGBA: int = 6
