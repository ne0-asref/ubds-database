"""Elm-style error formatter for jsonschema ValidationErrors.

Renders schema validation failures as friendly, fix-oriented blocks:

    ✗ <file_path>
      ├─ field:    <dotted.path>
      ├─ expected: <human description>
      ├─ got:      <repr> (<type>)
      ├─ at:       line N, column M
      └─ fix:      <hint>

The ``at:`` line is computed by walking the YAML node tree produced by
``yaml.compose()`` so we can map a jsonschema ``absolute_path`` back to a
source location. If no yaml text is provided (or the path can't be resolved),
the ``at:`` line is omitted rather than crashing.
"""
from __future__ import annotations

from typing import Any, Iterable, List, Optional

import yaml
from jsonschema import ValidationError

# ---------------------------------------------------------------------------
# Fix hints (≥10 validators)
# ---------------------------------------------------------------------------

FIX_HINTS: dict[str, str] = {
    "required": "Add the missing field to your YAML. Check the spec for which fields are mandatory.",
    "enum": "Use one of the allowed values listed above. Values are case-sensitive.",
    "pattern": "Value must match the required regex. Check formatting (case, separators, allowed characters).",
    "type": "Change the value to the expected type. YAML quotes can turn numbers into strings — remove them if needed.",
    "minimum": "Increase the value so it meets the minimum allowed.",
    "maximum": "Decrease the value so it stays under the maximum allowed.",
    "minItems": "Add at least one more item to this list — empty or short lists aren't allowed here.",
    "maxItems": "Remove items so the list fits within the maximum length.",
    "minLength": "The string is too short — provide a longer value.",
    "maxLength": "The string is too long — shorten it to fit the maximum length.",
    "format": "Reformat the value to match the expected format (e.g. ISO date YYYY-MM-DD, valid URI).",
    "additionalProperties": "Remove the unexpected property, or check for a typo in the field name.",
    "dependencies": "This field requires another field to also be present. Add the dependent field.",
    "uniqueItems": "Remove duplicate entries from the list.",
}

_SLUG_PATTERN_HINT = (
    "Use lowercase letters, digits, and hyphens; must start and end with alphanumeric."
)


# ---------------------------------------------------------------------------
# Field path
# ---------------------------------------------------------------------------

def _format_path(path: Iterable) -> str:
    parts: List[str] = []
    for elem in path:
        if isinstance(elem, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{elem}]"
            else:
                parts.append(f"[{elem}]")
        else:
            parts.append(str(elem))
    if not parts:
        return "<root>"
    return ".".join(parts)


# ---------------------------------------------------------------------------
# Expected description
# ---------------------------------------------------------------------------

def _format_expected(err: ValidationError) -> str:
    v = err.validator
    val = err.validator_value
    if v == "type":
        if isinstance(val, list):
            return " or ".join(val)
        return str(val)
    if v == "enum":
        return "one of: " + ", ".join(repr(x) for x in val)
    if v == "required":
        # message is like: "'name' is a required property"
        missing = err.message.split("'")[1] if "'" in err.message else "?"
        return f'field "{missing}"'
    if v == "pattern":
        return f"string matching pattern {val}"
    if v == "format":
        return f"value with format '{val}'"
    if v == "minimum":
        return f"number >= {val}"
    if v == "maximum":
        return f"number <= {val}"
    if v == "minItems":
        return f"array with at least {val} item(s)"
    if v == "maxItems":
        return f"array with at most {val} item(s)"
    if v == "minLength":
        return f"string with length >= {val}"
    if v == "maxLength":
        return f"string with length <= {val}"
    if v == "additionalProperties":
        return "no additional properties"
    if v == "dependencies":
        return f"dependent fields: {val}"
    if v == "uniqueItems":
        return "unique items"
    return str(val)


# ---------------------------------------------------------------------------
# Got
# ---------------------------------------------------------------------------

def _format_got(err: ValidationError) -> str:
    inst = err.instance
    r = repr(inst)
    if len(r) > 60:
        r = r[:57] + "..."
    return f"{r} ({type(inst).__name__})"


# ---------------------------------------------------------------------------
# Source location lookup
# ---------------------------------------------------------------------------

def _locate(yaml_text: str, path: Iterable) -> Optional[tuple[int, int]]:
    try:
        node = yaml.compose(yaml_text)
    except Exception:
        return None
    if node is None:
        return None
    for elem in path:
        node = _descend(node, elem)
        if node is None:
            return None
    mark = node.start_mark
    return (mark.line + 1, mark.column + 1)


def _descend(node, key) -> Any:
    # MappingNode: node.value is list of (key_node, value_node)
    if hasattr(node, "value") and isinstance(node.value, list):
        # Mapping
        if node.value and isinstance(node.value[0], tuple):
            for k_node, v_node in node.value:
                if getattr(k_node, "value", None) == key:
                    return v_node
            return None
        # Sequence
        if isinstance(key, int) and 0 <= key < len(node.value):
            return node.value[key]
        return None
    return None


# ---------------------------------------------------------------------------
# Fix hint
# ---------------------------------------------------------------------------

_FALLBACK_FIX = "See spec/ubds-v1.schema.json for details."


def _format_fix(err: ValidationError) -> str:
    v = err.validator
    if v == "pattern":
        path_list = list(err.absolute_path)
        if path_list and path_list[-1] == "slug":
            return _SLUG_PATTERN_HINT
    return FIX_HINTS.get(v, _FALLBACK_FIX)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def format_error(
    validation_error: ValidationError,
    yaml_text: Optional[str],
    file_path: str,
) -> str:
    field = _format_path(validation_error.absolute_path)
    expected = _format_expected(validation_error)
    fix = _format_fix(validation_error)

    lines: List[str] = [f"\u2717 {file_path}"]
    lines.append(f"  \u251c\u2500 field:    {field}")
    lines.append(f"  \u251c\u2500 expected: {expected}")

    if validation_error.validator != "required":
        lines.append(f"  \u251c\u2500 got:      {_format_got(validation_error)}")

    loc = None
    if yaml_text is not None:
        loc = _locate(yaml_text, validation_error.absolute_path)
    if loc is not None:
        line_n, col_n = loc
        lines.append(f"  \u251c\u2500 at:       line {line_n}, column {col_n}")

    lines.append(f"  \u2514\u2500 fix:      {fix}")
    return "\n".join(lines)


def format_errors(
    validation_errors: list,
    yaml_text: Optional[str],
    file_path: str,
) -> str:
    return "\n\n".join(
        format_error(e, yaml_text, file_path) for e in validation_errors
    )
