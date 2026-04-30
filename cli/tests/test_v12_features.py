"""C22 U1 — positive + negative cases for each new v1.2 schema field.

Covers the five additive surfaces:

- Top-level ``aliases`` (array of non-empty strings, ``uniqueItems``).
- Top-level ``manufacturer_slug`` (kebab-case pattern).
- ``meta.confidence_skipped`` (array of section-name enum, ``uniqueItems``).
- ``meta.fetch_warnings`` (array of warning enum, ``uniqueItems``).
- ``meta.source_quality`` (object with ``per_source[]`` + scores in [0, 1]).

Plus a smoke test that ``spec/tests/examples/v1.2-features.ubds.yaml``
validates end-to-end against the v1.2 schema.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "spec" / "ubds-v1.schema.json"
EXAMPLE_PATH = REPO / "spec" / "tests" / "examples" / "v1.2-features.ubds.yaml"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def base_board() -> dict:
    """Minimal valid v1.2 board — required-field shell other tests mutate."""
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


def _expect_valid(schema: dict, doc: dict) -> None:
    jsonschema.validate(doc, schema)


def _expect_invalid(schema: dict, doc: dict) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)


# ---------------------------------------------------------------------------
# aliases
# ---------------------------------------------------------------------------

def test_aliases_accepts_array_of_strings(schema, base_board):
    base_board["aliases"] = ["Foo", "Bar"]
    _expect_valid(schema, base_board)


def test_aliases_accepts_empty_array(schema, base_board):
    base_board["aliases"] = []
    _expect_valid(schema, base_board)


def test_aliases_rejects_empty_string(schema, base_board):
    base_board["aliases"] = [""]
    _expect_invalid(schema, base_board)


def test_aliases_rejects_duplicate_entries(schema, base_board):
    base_board["aliases"] = ["x", "x"]
    _expect_invalid(schema, base_board)


# ---------------------------------------------------------------------------
# manufacturer_slug
# ---------------------------------------------------------------------------

def test_manufacturer_slug_accepts_kebab_case(schema, base_board):
    base_board["manufacturer_slug"] = "espressif"
    _expect_valid(schema, base_board)


def test_manufacturer_slug_accepts_multi_segment_kebab(schema, base_board):
    base_board["manufacturer_slug"] = "seeed-studio"
    _expect_valid(schema, base_board)


def test_manufacturer_slug_rejects_uppercase(schema, base_board):
    base_board["manufacturer_slug"] = "Espressif"
    _expect_invalid(schema, base_board)


def test_manufacturer_slug_rejects_underscore(schema, base_board):
    base_board["manufacturer_slug"] = "espressif_systems"
    _expect_invalid(schema, base_board)


# ---------------------------------------------------------------------------
# meta.confidence_skipped
# ---------------------------------------------------------------------------

def test_confidence_skipped_accepts_known_enum_subset(schema, base_board):
    base_board["meta"]["confidence_skipped"] = ["pinout", "certifications"]
    _expect_valid(schema, base_board)


def test_confidence_skipped_accepts_empty_array(schema, base_board):
    base_board["meta"]["confidence_skipped"] = []
    _expect_valid(schema, base_board)


def test_confidence_skipped_rejects_unknown_enum(schema, base_board):
    base_board["meta"]["confidence_skipped"] = ["xyz"]
    _expect_invalid(schema, base_board)


def test_confidence_skipped_rejects_duplicates(schema, base_board):
    base_board["meta"]["confidence_skipped"] = ["pinout", "pinout"]
    _expect_invalid(schema, base_board)


# ---------------------------------------------------------------------------
# meta.fetch_warnings
# ---------------------------------------------------------------------------

def test_fetch_warnings_accepts_known_enum_subset(schema, base_board):
    base_board["meta"]["fetch_warnings"] = ["single-source", "search-mode-fallback"]
    _expect_valid(schema, base_board)


def test_fetch_warnings_rejects_unknown_enum(schema, base_board):
    base_board["meta"]["fetch_warnings"] = ["unknown"]
    _expect_invalid(schema, base_board)


def test_fetch_warnings_rejects_duplicates(schema, base_board):
    base_board["meta"]["fetch_warnings"] = ["single-source", "single-source"]
    _expect_invalid(schema, base_board)


# ---------------------------------------------------------------------------
# meta.source_quality
# ---------------------------------------------------------------------------

def test_source_quality_accepts_full_object(schema, base_board):
    base_board["meta"]["source_quality"] = {
        "per_source": [
            {"url": "https://example.com/a", "score": 0.8, "tier": "primary"},
            {"url": "https://example.com/b", "score": 0.4, "tier": "secondary"},
        ],
        "aggregate_score": 0.6,
        "median_score": 0.6,
    }
    _expect_valid(schema, base_board)


def test_source_quality_accepts_minimal_per_source(schema, base_board):
    base_board["meta"]["source_quality"] = {
        "per_source": [{"url": "https://example.com/a", "score": 0.5}],
    }
    _expect_valid(schema, base_board)


def test_source_quality_rejects_score_above_one(schema, base_board):
    base_board["meta"]["source_quality"] = {
        "per_source": [{"url": "https://example.com/a", "score": 1.5}],
    }
    _expect_invalid(schema, base_board)


def test_source_quality_rejects_score_below_zero(schema, base_board):
    base_board["meta"]["source_quality"] = {
        "per_source": [{"url": "https://example.com/a", "score": -0.1}],
    }
    _expect_invalid(schema, base_board)


def test_source_quality_rejects_unknown_tier(schema, base_board):
    base_board["meta"]["source_quality"] = {
        "per_source": [{"url": "https://example.com/a", "score": 0.5, "tier": "gold"}],
    }
    _expect_invalid(schema, base_board)


def test_source_quality_rejects_aggregate_above_one(schema, base_board):
    base_board["meta"]["source_quality"] = {"aggregate_score": 1.1}
    _expect_invalid(schema, base_board)


def test_source_quality_rejects_per_source_without_url(schema, base_board):
    base_board["meta"]["source_quality"] = {
        "per_source": [{"score": 0.5}],
    }
    _expect_invalid(schema, base_board)


# ---------------------------------------------------------------------------
# Example file
# ---------------------------------------------------------------------------

def test_example_file_exists():
    assert EXAMPLE_PATH.is_file(), f"missing example fixture: {EXAMPLE_PATH}"


def test_example_file_validates(schema):
    data = yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))
    _expect_valid(schema, data)


def test_example_exercises_every_new_field(schema):
    """Sanity — the example must include every v1.2 surface, otherwise the
    features test suite isn't actually covering the example."""
    data = yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))
    assert "aliases" in data
    assert "manufacturer_slug" in data
    assert "confidence_skipped" in data["meta"]
    assert "fetch_warnings" in data["meta"]
    assert "source_quality" in data["meta"]


# ---------------------------------------------------------------------------
# Reference YAML
# ---------------------------------------------------------------------------

def test_reference_yaml_is_v12():
    """`spec/ubds-v1.reference.ubds.yaml` declares ubds_version 1.2."""
    ref = REPO / "spec" / "ubds-v1.reference.ubds.yaml"
    data = yaml.safe_load(ref.read_text(encoding="utf-8"))
    assert data["ubds_version"] == "1.2"


def test_reference_yaml_validates(schema):
    """Reference YAML must validate against the v1.2 schema."""
    ref = REPO / "spec" / "ubds-v1.reference.ubds.yaml"
    data = yaml.safe_load(ref.read_text(encoding="utf-8"))
    _expect_valid(schema, copy.deepcopy(data))
