"""C22 U5 — meta.confidence_skipped <-> meta.confidence mutual exclusion.

A section name listed in ``meta.confidence_skipped`` (sections the UI hides
outright instead of rendering low-confidence) must NOT also appear as a key
under ``meta.confidence`` (per-section verification confidence). Documenting
both for the same section is contradictory: it tells the UI to hide a section
while simultaneously claiming a confidence value for it.

Schema (U1) accepts each field in isolation. The mutual-exclusion rule is a
cross-field invariant the Python validator enforces here.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from dbf.cli import main
from dbf.validate import validate_file


def _base_board() -> dict:
    """Minimal valid v1.2 board the cross-field tests mutate."""
    return {
        "ubds_version": "1.2",
        "name": "Test Board",
        "slug": "test-board",
        "manufacturer": "Test Manufacturer",
        "board_type": ["MCU"],
        "meta": {
            "sources": ["https://example.com/test-board"],
            "product_url": "https://example.com/test-board",
        },
    }


def _write(tmp_path: Path, doc: dict, name: str = "board.ubds.yaml") -> Path:
    target = tmp_path / name
    target.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Pass cases — only one side present (or neither).
# ---------------------------------------------------------------------------

def test_confidence_skipped_only_passes(tmp_path):
    doc = _base_board()
    doc["meta"]["confidence_skipped"] = ["pinout", "certifications"]
    path = _write(tmp_path, doc)
    result = validate_file(path)
    assert result.ok, f"unexpected errors: {[e.message for e in result.errors]}"


def test_confidence_only_passes(tmp_path):
    doc = _base_board()
    doc["meta"]["confidence"] = {"processing": "high", "interfaces": "medium"}
    path = _write(tmp_path, doc)
    result = validate_file(path)
    assert result.ok, f"unexpected errors: {[e.message for e in result.errors]}"


def test_neither_field_passes(tmp_path):
    """Neither documented yet — board is valid, validator stays silent."""
    doc = _base_board()
    path = _write(tmp_path, doc)
    result = validate_file(path)
    assert result.ok, f"unexpected errors: {[e.message for e in result.errors]}"


def test_disjoint_sets_pass(tmp_path):
    """Both fields present but no section appears in both — should pass."""
    doc = _base_board()
    doc["meta"]["confidence"] = {"processing": "high", "interfaces": "high"}
    doc["meta"]["confidence_skipped"] = ["pinout", "certifications"]
    path = _write(tmp_path, doc)
    result = validate_file(path)
    assert result.ok, f"unexpected errors: {[e.message for e in result.errors]}"


# ---------------------------------------------------------------------------
# Reject cases — same section in both.
# ---------------------------------------------------------------------------

def test_same_section_in_both_rejects(tmp_path):
    doc = _base_board()
    doc["meta"]["confidence"] = {"pinout": "low"}
    doc["meta"]["confidence_skipped"] = ["pinout"]
    path = _write(tmp_path, doc)
    result = validate_file(path)
    assert not result.ok
    messages = " ".join(e.message for e in result.errors)
    assert "pinout" in messages
    assert "confidence_skipped" in messages
    assert "confidence" in messages


def test_overlap_error_names_each_section(tmp_path):
    """When multiple sections overlap, every section must appear in some error."""
    doc = _base_board()
    doc["meta"]["confidence"] = {
        "pinout": "low",
        "certifications": "medium",
        "interfaces": "high",
    }
    doc["meta"]["confidence_skipped"] = ["pinout", "certifications"]
    path = _write(tmp_path, doc)
    result = validate_file(path)
    assert not result.ok
    messages = " ".join(e.message for e in result.errors)
    assert "pinout" in messages
    assert "certifications" in messages
    # "interfaces" only appears in confidence — not in skipped — so no error
    # *about interfaces* should fire. The token may still appear inside a
    # different unrelated message in theory, but the only errors here are the
    # mutual-exclusion ones, so check the count of overlap-flagged sections.
    overlap_errors = [e for e in result.errors if "confidence_skipped" in e.message]
    assert len(overlap_errors) == 2


def test_cli_validate_rejects_with_clear_message(runner, tmp_path):
    """Full CLI surface: dbf validate ... exits 1 and surfaces the rule."""
    doc = _base_board()
    doc["meta"]["confidence"] = {"wireless": "medium"}
    doc["meta"]["confidence_skipped"] = ["wireless"]
    path = _write(tmp_path, doc)
    r = runner.invoke(main, ["validate", str(path)])
    assert r.exit_code == 1, r.output
    assert "wireless" in r.output
    assert "confidence_skipped" in r.output


def test_cli_validate_json_includes_overlap(runner, tmp_path):
    """JSON output mode must surface the cross-field error too."""
    import json as _json

    doc = _base_board()
    doc["meta"]["confidence"] = {"power": "low"}
    doc["meta"]["confidence_skipped"] = ["power"]
    path = _write(tmp_path, doc)
    r = runner.invoke(main, ["validate", "--json", str(path)])
    assert r.exit_code == 1, r.output
    payload = _json.loads(r.output)
    assert isinstance(payload, list) and payload
    messages = " ".join(e["message"] for e in payload[0]["errors"])
    assert "power" in messages
    assert "confidence_skipped" in messages
