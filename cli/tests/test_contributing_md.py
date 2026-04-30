"""Scope-policy drift tests for CONTRIBUTING.md (C22 U9).

UBDS v1.x covers boards with their own MCU/SoC (MCU, SBC, SoM) and
carrier/expansion boards (``board_type: Carrier`` or ``Expansion``).
Sensor-only breakouts are out of scope until a future cycle adds
dedicated ``board_type`` enum values; until then, CONTRIBUTING.md must
state the policy so contributors don't file bare sensor modules and
get bounced at review.

These assertions are deliberately phrase-level rather than wording-level
so the docs author can polish surrounding prose without breaking the
suite — but the load-bearing phrases the spec calls out (the
"boards with their own MCU/SoC" gate, the Carrier/Expansion
alternatives, and the explicit sensor-breakout out-of-scope marker)
must always be present.

Run::

    pytest cli/tests/test_contributing_md.py -v
"""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _contributing() -> str:
    return (REPO_ROOT / "CONTRIBUTING.md").read_text()


def test_scope_includes_mcu_soc_phrase():
    """The MCU/SoC gate phrase must appear verbatim — V-gate from spec.md."""
    assert "boards with their own MCU/SoC" in _contributing()


def test_scope_lists_carrier_and_expansion_alternatives():
    """Carrier and Expansion must both be named as the catch-all classes."""
    text = _contributing()
    assert "Carrier" in text
    assert "Expansion" in text


def test_scope_marks_sensor_breakouts_out_of_scope():
    """Sensor-only breakouts must be explicitly called out as out of scope."""
    low = _contributing().lower()
    assert "sensor" in low
    assert "out of scope" in low or "out-of-scope" in low
