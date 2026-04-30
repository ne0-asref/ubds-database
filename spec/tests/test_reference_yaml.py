"""Drift guardrail: reference YAML must validate against the schema."""
import pathlib
import yaml
from conftest import SPEC_DIR

REFERENCE = SPEC_DIR / "ubds-v1.reference.ubds.yaml"


def test_reference_yaml_parses():
    doc = yaml.safe_load(REFERENCE.read_text())
    assert isinstance(doc, dict)


def test_reference_yaml_validates_against_schema(validator):
    doc = yaml.safe_load(REFERENCE.read_text())
    validator.validate(doc)


def test_reference_yaml_validates_at_v12(validator):
    """v1.2: reference must declare ubds_version 1.2, carry meta.product_url,
    and have no top-level pricing block. v1.1 boards still pass the schema —
    the additive-only iron rule lives in cli/tests/test_v12_back_compat.py."""
    doc = yaml.safe_load(REFERENCE.read_text())
    assert doc.get("ubds_version") == "1.2"
    assert "pricing" not in doc
    assert "product_url" in doc.get("meta", {})
    validator.validate(doc)


def test_reference_yaml_uses_every_top_level_section():
    doc = yaml.safe_load(REFERENCE.read_text())
    expected = {
        "ubds_version", "name", "slug", "manufacturer", "board_type",
        "processing", "wireless", "software", "physical",
        "meta", "metadata",
    }
    missing = expected - set(doc.keys())
    assert not missing, f"reference YAML missing top-level sections: {missing}"
