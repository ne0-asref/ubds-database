# UBDS — Universal Board Description Standard

UBDS is a portable, human-readable standard for describing embedded development
boards. Author boards in YAML, validate against the JSON Schema, and ingest
into any backend.

**Current version: 1.1** — commerce separation. Pricing, vendors, and
affiliate data are **not** part of UBDS; they live in the devboardfinder
`board_sellers` table. See [CHANGELOG.md](CHANGELOG.md) for the full migration
note.

## Required meta fields

Every `.ubds.yaml` file must include the following under `meta`:

| field          | type           | notes                                                                 |
|----------------|----------------|-----------------------------------------------------------------------|
| `sources`      | array of URIs  | At least one verifiable primary source (datasheet, manufacturer page) |
| `product_url`  | URI            | Canonical manufacturer product page — not a reseller or affiliate     |

## Files

- `ubds-v1.schema.json` — the canonical machine-readable schema (JSON Schema Draft-07).
- `ubds-v1.reference.ubds.yaml` — the canonical human-readable reference doc
  (annotated NVIDIA Jetson Orin Nano example with comments documenting every
  field). Validates against the schema; CI guards drift between the two.
- `CHANGELOG.md` — versioned change history.
- `tests/` — pytest suite (no network, no Supabase, no `dbf` CLI dependency).

## Validate locally

```bash
cd spec
pip install -r tests/requirements.txt
python -c "
import json, yaml
from jsonschema import Draft7Validator, FormatChecker
schema = json.load(open('ubds-v1.schema.json'))
doc = yaml.safe_load(open('ubds-v1.reference.ubds.yaml'))
Draft7Validator(schema, format_checker=FormatChecker()).validate(doc)
print('OK')
"
```

Or run the full test suite:

```bash
cd spec
pip install -r tests/requirements.txt
pytest tests/ -v
```

## Versioning

See [CHANGELOG.md](CHANGELOG.md). The schema follows semver within v1.x —
additive changes only; breaking changes require a major bump.

## Phase 1 follow-up

Submitting this schema to [SchemaStore.org](https://www.schemastore.org/) for
out-of-the-box VS Code YAML extension validation is a planned Phase 1 follow-up
task. Requires the schema to be merged and publicly hosted first.
