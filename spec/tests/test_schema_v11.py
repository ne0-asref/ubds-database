"""UBDS v1.1 commerce-separation tests.

Validates:
- meta.product_url is required and must be a URI
- legacy top-level `pricing` blocks are rejected
- ubds_version pattern still accepts 1.0 and 1.1 (version semantics live in C3)
"""
import json
import pathlib

import pytest
import yaml
from jsonschema import Draft7Validator, FormatChecker, ValidationError

SPEC_DIR = pathlib.Path(__file__).parent.parent


@pytest.fixture(scope="module")
def v11_schema():
    return json.loads((SPEC_DIR / "ubds-v1.schema.json").read_text())


@pytest.fixture(scope="module")
def v11_validator(v11_schema):
    return Draft7Validator(v11_schema, format_checker=FormatChecker())


MINIMAL_V11_YAML = """\
ubds_version: "1.1"
name: "Minimal v1.1 Board"
slug: "minimal-v11-board"
manufacturer: "Test Co"
board_type:
  - MCU
meta:
  sources:
    - "https://example.com/datasheet"
  product_url: "https://www.raspberrypi.com/products/raspberry-pi-5/"
"""


def _load(yaml_text):
    return yaml.safe_load(yaml_text)


def test_valid_v11_board_passes(v11_validator):
    doc = _load(MINIMAL_V11_YAML)
    v11_validator.validate(doc)


def test_missing_product_url_fails(v11_validator):
    doc = _load(MINIMAL_V11_YAML)
    del doc["meta"]["product_url"]
    with pytest.raises(ValidationError) as exc:
        v11_validator.validate(doc)
    assert "product_url" in str(exc.value)


def test_non_uri_product_url_fails(v11_schema):
    validator = Draft7Validator(v11_schema, format_checker=FormatChecker())
    doc = _load(MINIMAL_V11_YAML)
    doc["meta"]["product_url"] = "not a url"
    with pytest.raises(ValidationError) as exc:
        validator.validate(doc)
    msg = str(exc.value).lower()
    assert "uri" in msg or "format" in msg


def test_legacy_pricing_rejected(v11_validator):
    doc = _load(MINIMAL_V11_YAML)
    doc["pricing"] = {"msrp_usd": 10, "vendors": []}
    with pytest.raises(ValidationError):
        v11_validator.validate(doc)


def test_version_pattern_unchanged(v11_validator):
    doc = _load(MINIMAL_V11_YAML)
    doc["ubds_version"] = "1.0"
    v11_validator.validate(doc)
