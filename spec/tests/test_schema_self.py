"""Meta tests: schema is itself valid Draft-07 JSON."""
import json
from jsonschema import Draft7Validator
from conftest import SPEC_DIR

SCHEMA_PATH = SPEC_DIR / "ubds-v1.schema.json"


def test_schema_is_valid_json():
    json.loads(SCHEMA_PATH.read_text())


def test_schema_is_valid_draft07(schema):
    Draft7Validator.check_schema(schema)


def test_schema_dialect_is_draft07(schema):
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"


def test_schema_has_top_level_required(schema):
    required = set(schema["required"])
    assert required >= {"ubds_version", "name", "slug", "manufacturer", "board_type", "meta"}
