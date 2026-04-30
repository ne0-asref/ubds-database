"""UBDS JSON Schema loader.

The board schema ships as package data under ``dbf/data/ubds-v1.schema.json``
so installed wheels work outside the source tree. In editable/dev mode we
fall back to the canonical copy in ``spec/ubds-v1.schema.json`` at the repo
root. The C22 U3 manufacturer schema (``ubds-manufacturer.schema.json``)
follows the same lookup convention.
"""
from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

BUNDLED_VERSION = "1.1"

_SCHEMA_RESOURCE = "data/ubds-v1.schema.json"
_MANUFACTURER_SCHEMA_RESOURCE = "data/ubds-manufacturer.schema.json"


def _load_packaged_or_spec(resource: str, spec_filename: str) -> dict:
    pkg = files("dbf").joinpath(resource)
    if pkg.is_file():
        return json.loads(pkg.read_text(encoding="utf-8"))
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "spec" / spec_filename
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        f"schema not found in package data ({resource}) or "
        f"repo spec/{spec_filename}"
    )


def load_schema() -> dict:
    """Return the bundled UBDS v1 JSON schema as a dict."""
    return _load_packaged_or_spec(_SCHEMA_RESOURCE, "ubds-v1.schema.json")


def load_manufacturer_schema() -> dict:
    """Return the bundled UBDS manufacturer index JSON schema as a dict.

    Added in C22 U3. Used by :func:`dbf.validate.validate_manufacturers` to
    schema-check ``manufacturers/<slug>.yaml`` files alongside board YAMLs.
    """
    return _load_packaged_or_spec(
        _MANUFACTURER_SCHEMA_RESOURCE, "ubds-manufacturer.schema.json"
    )
