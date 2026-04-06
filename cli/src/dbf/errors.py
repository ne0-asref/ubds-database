"""Elm-style error formatting for UBDS validation errors."""

from dataclasses import dataclass, field


@dataclass
class ValidationError:
    """A structured validation error with context for humans."""
    field: str
    message: str
    expected: str | None = None
    got: str | None = None
    fix_suggestion: str | None = None


def format_validation_error(
    field_path: str,
    message: str,
    validator: str,
    schema_path: list[str],
    instance: object,
) -> ValidationError:
    """Convert a raw jsonschema error into an Elm-style structured error."""

    err_field = field_path
    expected = None
    got = None
    fix_suggestion = None

    if validator == "required":
        # Extract the missing field name from the message
        missing = message.split("'")[1] if "'" in message else message
        err_field = missing
        expected = f"field '{missing}' is required"
        got = "missing"
        fix_suggestion = f"Add '{missing}' to your board YAML."

    elif validator == "enum":
        # Extract enum values from schema_path context
        got = repr(instance)
        # Try to extract allowed values from the message
        if "is not one of" in message:
            allowed = message.split("is not one of")[1].strip()
            expected = f"one of {allowed}"
        else:
            expected = "a valid enum value"
        fix_suggestion = f"Change '{err_field}' to {expected}."

    elif validator == "type":
        got = type(instance).__name__
        # Extract expected type from message
        if "is not of type" in message:
            expected_type = message.split("is not of type")[1].strip().strip("'\"")
            expected = expected_type
        else:
            expected = "correct type"
        fix_suggestion = f"Change '{err_field}' to type {expected}."

    elif validator == "minItems":
        got = f"array with {len(instance)} items" if isinstance(instance, list) else repr(instance)
        expected = "non-empty array"
        fix_suggestion = f"Add at least one item to '{err_field}'."

    elif validator == "const":
        got = repr(instance)
        expected = message.split("was expected")[0].strip() if "was expected" in message else "expected value"
        fix_suggestion = f"Set '{err_field}' to the expected value."

    elif validator == "pattern":
        got = repr(instance)
        expected = "matching pattern"
        fix_suggestion = f"Fix the format of '{err_field}'."

    elif validator == "minimum" or validator == "maximum":
        got = repr(instance)
        expected = message
        fix_suggestion = f"Adjust the value of '{err_field}'."

    elif validator == "additionalProperties":
        got = repr(instance)
        expected = "no additional properties"
        fix_suggestion = f"Remove unexpected field from '{err_field}'."

    else:
        got = repr(instance)
        expected = None
        fix_suggestion = f"Fix '{err_field}': {message}"

    return ValidationError(
        field=err_field,
        message=message,
        expected=expected,
        got=got,
        fix_suggestion=fix_suggestion,
    )
