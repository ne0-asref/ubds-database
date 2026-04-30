"""C22 U8 — PR template + CONTRIBUTING.md must reflect v1.2 conventions.

The PR template gains three checklist items covering the new nested
``boards/<manufacturer-slug>/<board-slug>.ubds.yaml`` layout, the
``manufacturers/<slug>.yaml`` index, and the ``ubds_version: 1.2`` bump
gate. CONTRIBUTING.md gains a new "Adding a manufacturer" section and an
"Adding a board" cross-link to ``onboard_components.cameras[]`` so that
contributors who ship a camera-integrated board (ESP32-CAM, Pi camera
HAT) don't miss it.

Assertions are phrase-level so prose can evolve, but the load-bearing
strings the V-gates grep for must always be present.

Run::

    pytest cli/tests/test_pr_template.py -v
"""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _pr_template() -> str:
    return (REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text()


def _contributing() -> str:
    return (REPO_ROOT / "CONTRIBUTING.md").read_text()


# ---------------------------------------------------------------------------
# PR template — three new checklist items (V-gates OK_PR_NESTED, OK_PR_MFR,
# OK_PR_V12).
# ---------------------------------------------------------------------------

def test_pr_template_mentions_nested_board_layout():
    """V-gate OK_PR_NESTED: ``<manufacturer-slug>/<board-slug>`` appears."""
    assert re.search(r"manufacturer-slug.*board-slug", _pr_template())


def test_pr_template_mentions_manufacturer_index():
    """V-gate OK_PR_MFR: ``manufacturers/<slug>`` appears."""
    assert "manufacturers/<slug>" in _pr_template()


def test_pr_template_mentions_v12_bump():
    """V-gate OK_PR_V12: literal phrase ``ubds_version bumped to 1.2``."""
    assert "ubds_version bumped to 1.2" in _pr_template()


def _bullet_blocks(text: str) -> list[str]:
    """Group Markdown bullets into single strings, joining continuation lines.

    A new bullet starts at column 0 with ``- [`` (checkbox) or ``- ``
    (plain). Indented continuation lines belong to the preceding bullet.
    """
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("- "):
            if current:
                blocks.append("\n".join(current))
            current = [line]
        elif current and (line.startswith("  ") or line.startswith("\t")):
            current.append(line)
        else:
            if current:
                blocks.append("\n".join(current))
                current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def test_pr_template_new_items_are_actual_checklist_items():
    """Each new item must live inside a Markdown checkbox bullet, not prose."""
    blocks = _bullet_blocks(_pr_template())
    checklist_blocks = [b for b in blocks if b.startswith("- [ ]")]

    assert any(
        "manufacturer-slug" in b and "board-slug" in b for b in checklist_blocks
    ), "nested-layout phrase must be inside a `- [ ]` bullet"

    assert any(
        "manufacturers/<slug>" in b for b in checklist_blocks
    ), "manufacturer-index phrase must be inside a `- [ ]` bullet"

    assert any(
        "ubds_version bumped to 1.2" in b for b in checklist_blocks
    ), "v1.2-bump phrase must be inside a `- [ ]` bullet"


# ---------------------------------------------------------------------------
# CONTRIBUTING.md — nested layout + manufacturer section + cameras bullet
# (V-gates OK_CONTRIB_MFR, OK_CONTRIB_CAM).
# ---------------------------------------------------------------------------

def test_contributing_uses_nested_board_layout():
    """Board-path examples must use ``boards/<manufacturer-slug>/<board-slug>``."""
    text = _contributing()
    assert re.search(
        r"boards/<manufacturer-slug>/<[a-z-]*slug>\.ubds\.yaml", text
    ), "CONTRIBUTING.md still uses flat boards/<slug>.ubds.yaml layout"


def test_contributing_has_adding_a_manufacturer_section():
    """V-gate OK_CONTRIB_MFR: ``Adding a manufacturer`` section exists."""
    text = _contributing()
    assert "Adding a manufacturer" in text
    assert re.search(r"^#+\s+Adding a manufacturer\s*$", text, re.MULTILINE), (
        "'Adding a manufacturer' must be a Markdown heading"
    )


def test_contributing_manufacturer_section_describes_yaml_format():
    """Manufacturer section must mention ``manufacturers/<slug>.yaml``."""
    assert "manufacturers/<slug>.yaml" in _contributing()


def test_contributing_manufacturer_section_describes_add_criterion():
    """Manufacturer section must describe the add-criterion (well_known or referenced)."""
    text = _contributing().lower()
    assert "well_known" in text
    assert "canonical_name" in _contributing()


def test_contributing_mentions_camera_bullet_for_boards():
    """V-gate OK_CONTRIB_CAM: ``onboard_components.cameras`` is referenced."""
    assert "onboard_components.cameras" in _contributing()


def test_contributing_camera_bullet_distinguishes_connector_from_sensor():
    """The bullet must clarify integrated camera vs bare connector."""
    text = _contributing()
    assert re.search(
        r"integrated camera.*connector|connector.*integrated camera",
        text,
        re.IGNORECASE | re.DOTALL,
    ), "CONTRIBUTING must distinguish integrated cameras from bare connectors"
