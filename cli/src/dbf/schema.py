"""UBDS JSON Schema loader.

The schema ships as package data under ``dbf/data/ubds-v1.schema.json`` so
installed wheels work outside the source tree. In editable/dev mode we fall
back to the canonical copy in ``spec/ubds-v1.schema.json`` at the repo root.
"""
from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

BUNDLED_VERSION = "1.1"

_SCHEMA_RESOURCE = "data/ubds-v1.schema.json"


def load_schema() -> dict:
    """Return the bundled UBDS v1 JSON schema as a dict."""
    resource = files("dbf").joinpath(_SCHEMA_RESOURCE)
    if resource.is_file():
        return json.loads(resource.read_text(encoding="utf-8"))

    # Dev fallback: walk up from this file looking for spec/ubds-v1.schema.json
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "spec" / "ubds-v1.schema.json"
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))

    raise FileNotFoundError(
        "UBDS schema not found in package data or repo spec/ directory"
    )
