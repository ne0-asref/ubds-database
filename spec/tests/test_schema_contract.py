"""Contract tests: every field C5 will flatten must exist in the schema."""
import pytest


FLATTENING_CONTRACT = [
    ("/properties/name", "string"),
    ("/properties/slug", "string"),
    ("/properties/manufacturer", "string"),
    ("/properties/board_type", "array"),
    ("/properties/status", "string"),
    ("/properties/difficulty_level", "string"),
    ("/properties/processing/items/properties/cpu_cores/items/properties/architecture", "string"),
    ("/properties/processing/items/properties/cpu_cores/items/properties/count", "integer"),
    ("/properties/processing/items/properties/cpu_cores/items/properties/clock_mhz", "integer"),
    ("/properties/processing/items/properties/memory/properties/ram_kb", "integer"),
    ("/properties/processing/items/properties/memory/properties/flash_kb", "integer"),
    ("/properties/wireless/items/properties/protocol", "string"),
    ("/properties/software/properties/frameworks/items/properties/name", "string"),
    ("/properties/software/properties/languages/items/properties/name", "string"),
    ("/properties/physical/properties/form_factor", "array"),
    ("/properties/use_cases", "array"),
    ("/properties/tags", "array"),
    ("/properties/meta/properties/product_url", "string"),
    ("/properties/meta/properties/data_completeness", "string"),
    ("/properties/meta/properties/community_reviewed", "boolean"),
    ("/properties/meta/properties/verified", "boolean"),
    ("/properties/parent_board", ["string", "null"]),
    ("/properties/metadata/properties/image_url", "string"),
    ("/properties/metadata/properties/top_view", "boolean"),
]


def _walk(schema, pointer):
    """Inline JSON pointer walker (no external dep)."""
    if pointer == "":
        return schema
    parts = pointer.split("/")[1:]
    node = schema
    for p in parts:
        p = p.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or p not in node:
            return None
        node = node[p]
    return node


@pytest.mark.parametrize("path,expected_type", FLATTENING_CONTRACT)
def test_every_contract_field_exists_in_schema(schema, path, expected_type):
    node = _walk(schema, path)
    assert node is not None, f"contract field missing from schema: {path} (expected type {expected_type})"


@pytest.mark.parametrize("path,expected_type", FLATTENING_CONTRACT)
def test_every_contract_field_has_expected_type(schema, path, expected_type):
    node = _walk(schema, path)
    assert node is not None, f"contract field missing: {path}"
    actual = node.get("type")
    if isinstance(expected_type, list):
        assert isinstance(actual, list) and set(actual) == set(expected_type), (
            f"path {path}: expected type {expected_type}, got {actual}"
        )
    else:
        # Accept either exact match or a nullable variant ["<type>", "null"].
        if isinstance(actual, list):
            assert expected_type in actual, (
                f"path {path}: expected type {expected_type!r} in {actual!r}"
            )
        else:
            assert actual == expected_type, (
                f"path {path}: expected type {expected_type!r}, got {actual!r}"
            )


def test_no_contract_field_dropped():
    assert len(FLATTENING_CONTRACT) == 24
