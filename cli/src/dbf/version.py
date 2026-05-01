"""ubds_version compatibility check.

Compares a board file's declared ``ubds_version`` against the schema version
bundled with this CLI build. Returns a 3-state level so callers can decide
how loud to be:

* ``("ok", "")`` — exact match, OR board declares an older minor version
  than the bundled schema. Older boards are explicitly supported per the
  back-compat design: schema minors are additive, so a v1.1 board validates
  cleanly against a v1.2 CLI. Boards bump their own ``ubds_version`` only
  when they start using fields introduced in a newer minor (see
  CONTRIBUTING.md §"When to bump ubds_version").
* ``("warn", msg)`` — board declares a NEWER minor than the CLI knows about.
  CLI may not validate fields the board uses; surface a notice and suggest
  upgrading dbf.
* ``("error", msg)`` — different major, or unparseable version string.
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

    if board[0] != bundled[0]:
        return (
            "error",
            (
                f"ubds_version {board_version} has a different major version than "
                f"the CLI's bundled schema (v{BUNDLED_VERSION}); upgrade dbf or "
                f"downgrade the board file"
            ),
        )

    if board[1] <= bundled[1]:
        # Same major; board's minor is at or below the CLI's. Older minor is
        # explicitly fine — schema minors are additive and the CLI validates
        # against its bundled (newer) schema, which is a superset.
        return ("ok", "")

    return (
        "warn",
        (
            f"ubds_version {board_version} is newer than the CLI's bundled schema "
            f"(v{BUNDLED_VERSION}); fields added after v{BUNDLED_VERSION} will not "
            f"be validated. Upgrade dbf to silence this warning."
        ),
    )
