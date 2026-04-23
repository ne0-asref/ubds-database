"""Docs-hygiene drift tests for the C21.6 contributor-facing surfaces.

These assertions mirror the ten Tier-1 + one Tier-2 cases in
``artifacts/test-matrix.md §C21.6``. They verify that the docs surfaces
C21.6 ships — ``CONTRIBUTING.md §Adding a board image``, the README
pointer, and ``.github/PULL_REQUEST_TEMPLATE.md`` — contain the
grep-testable content the spec requires, so contributors always see a
consistent board-image workflow.

The cross-file drift check against ``cli/src/dbf/constants.py`` lives in
``test_canonical_vocab.py`` (owned by C21.1); this module covers the
docs-file content that C21.1 could not yet assert.

Run::

    pytest cli/tests/test_docs_hygiene.py -v
"""
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _read(relpath: str) -> str:
    return (REPO_ROOT / relpath).read_text()


# ---------- Tier 1: grep-testable presence (10 cases) ----------


def test_contributing_has_image_section():
    assert "## Adding a board image" in _read("CONTRIBUTING.md")


def test_prefer_top_view_phrase():
    low = _read("CONTRIBUTING.md").lower()
    assert "prefer `top-view.png`" in low or "prefer top-view.png" in low


def test_pinout_is_distinct_asset():
    assert "distinct asset" in _read("CONTRIBUTING.md").lower()


def test_add_image_example_in_docs():
    text = _read("CONTRIBUTING.md")
    assert "dbf add-image" in text
    assert "--as top-view" in text


def test_check_images_command_in_docs():
    assert "dbf validate boards/ --check-images" in _read("CONTRIBUTING.md")


def test_readme_points_at_section():
    text = _read("README.md")
    assert "adding-a-board-image" in text.lower() or "Adding a board image" in text
    assert "CONTRIBUTING.md" in text


def test_pr_template_exists():
    assert (REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").is_file()


def test_pr_template_commit_prefixes():
    text = _read(".github/PULL_REQUEST_TEMPLATE.md")
    assert "feat(boards):" in text
    assert "fix(boards):" in text


def test_pr_template_check_images_command():
    assert "dbf validate boards/ --check-images" in _read(
        ".github/PULL_REQUEST_TEMPLATE.md"
    )


def test_pr_template_license_cc_by_4_0():
    text = _read(".github/PULL_REQUEST_TEMPLATE.md")
    assert "CC-BY-4.0" in text
    assert "meta.sources" in text


# ---------- Tier 2: structural hygiene (1 case) ----------


def _slugify(heading: str) -> str:
    s = heading.lower().strip()
    s = re.sub(r"[^a-z0-9 -]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s


def test_markdown_cross_file_anchors_resolve():
    """Any ``[...](CONTRIBUTING.md#anchor)`` link from README.md or the PR
    template must point at a real header in CONTRIBUTING.md. Catches the
    classic rename-the-header-forget-the-link drift.
    """
    contrib = _read("CONTRIBUTING.md")
    contrib_slugs = {
        _slugify(h) for h in re.findall(r"^#{1,6}\s+(.+)$", contrib, re.MULTILINE)
    }

    for path in ("README.md", ".github/PULL_REQUEST_TEMPLATE.md"):
        text = _read(path)
        for anchor in re.findall(r"\[[^\]]*\]\(CONTRIBUTING\.md#([^)]+)\)", text):
            assert anchor in contrib_slugs, (
                f"{path} links to CONTRIBUTING.md#{anchor} but no matching header exists"
            )
