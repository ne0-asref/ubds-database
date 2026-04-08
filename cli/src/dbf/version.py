"""ubds_version compatibility check.

Compares a board file's declared ``ubds_version`` against the schema version
bundled with this CLI build. Returns a 3-state level so callers can decide
how loud to be:

* ``("ok", "")`` — exact match
* ``("warn", msg)`` — same major, different minor (forward/backward compatible
  but caller should surface a notice)
* ``("error", msg)`` — different major, or unparseable version string
"""
from __future__ import annotations

from .schema import BUNDLED_VERSION


def _parse(version: str) -> tuple[int, int] | None:
    if not isinstance(version, str):
        return None
    parts = version.strip().split(".")
    if len(parts) < 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def check_version(board_version: str) -> tuple[str, str]:
    """Compare a board's ubds_version to the CLI's bundled schema version."""
    bundled = _parse(BUNDLED_VERSION)
    board = _parse(board_version)

    if bundled is None:
        # Should never happen — bundled constant is controlled by us.
        return ("error", f"bundled schema version {BUNDLED_VERSION!r} is invalid")

    if board is None:
        return (
            "error",
            f"ubds_version {board_version!r} is not a valid MAJOR.MINOR string",
        )

    if board == bundled:
        return ("ok", "")

    if board[0] != bundled[0]:
        return (
            "error",
            (
                f"ubds_version {board_version} has a different major version than "
                f"the CLI's bundled schema (v{BUNDLED_VERSION}); upgrade dbf or "
                f"downgrade the board file"
            ),
        )

    return (
        "warn",
        (
            f"ubds_version {board_version} differs from the CLI's bundled schema "
            f"(v{BUNDLED_VERSION}); validation will use v{BUNDLED_VERSION} rules"
        ),
    )
