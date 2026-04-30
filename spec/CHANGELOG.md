# UBDS Changelog

## v1.2.0 — 2026-04-30

Additive expansion. No breaking changes; every v1.1 board validates
under v1.2 unchanged. `ubds_version` pattern stays `^1\.\d+$` so boards
authored against v1.1 continue to pass.

### Added
- Top-level `aliases` (array of non-empty strings, `uniqueItems: true`) —
  alternate display names / common abbreviations for the board. Used by
  the frontend search index and (future) auto-redirect from old slugs.
- Top-level `manufacturer_slug` (kebab-case string, pattern
  `^[a-z0-9]+(-[a-z0-9]+)*$`) — pointer to a `manufacturers/<slug>.yaml`
  entry. Optional during v1.2 transition; the link + canonical_name
  match check lives in `dbf validate` (added in C22 U5).
- `meta.confidence_skipped` (array of section-name enum strings) — list
  of collapsible-row section IDs the UI should hide entirely instead of
  rendering with a low-confidence badge. Allowed values: `processing`,
  `interfaces`, `inputs-outputs`, `wireless`, `onboard`, `power`,
  `pinout`, `software`, `libraries`, `resources`, `thermal-physical`,
  `boot`, `compatible`, `certifications`. Per design decision D22.10 the
  frontend hides the row entirely. Mutually exclusive with
  `meta.confidence.<section>` for the same section name — a section
  listed in `confidence_skipped` MUST NOT also appear in `confidence`.
  JSON Schema cannot express that cross-field rule, so it's enforced by
  the Python validator (added in C22 U5).
- `meta.fetch_warnings` (array of warning enum strings, `uniqueItems`)
  — pipeline-side flags about source quality during ingestion. Allowed
  values: `low-quality-source-set`, `single-source`,
  `no-manufacturer-domain`, `search-mode-fallback`.
- `meta.source_quality` (object) — pipeline-side per-source scoring of
  each citation used during fetch. Holds `per_source[]` (each with
  required `url` + `score` and optional `tier` ∈ `primary | secondary |
  tertiary`), `aggregate_score`, and `median_score` (all in `[0, 1]`).
  Used by future pipeline triage tooling.
- (Carry-forward from 2026-04-23) `meta.image_filenames` — formalized
  in this release. Optional array enum of the five canonical
  board-image filename stems: `angle`, `block-diagram`, `bottom-view`,
  `pinout`, `top-view`. `uniqueItems: true`. Informational only; JSON
  Schema cannot validate filesystem contents, so the enum exists to
  advertise the vocabulary to downstream UBDS consumers. See
  `cli/src/dbf/constants.py::CANONICAL_IMAGE_FILENAMES` (the runtime
  source of truth) and `CONTRIBUTING.md §Adding a board image` for the
  contributor-facing reference.

### Filesystem (forward-pointer)
- Boards will nest under `boards/<manufacturer-slug>/<board-slug>.ubds.yaml`
  during the C22 PR B rollout (was flat `boards/<slug>.ubds.yaml`). The
  validator accepts both layouts during transition. A new
  `manufacturers/` directory will hold one entry per vendor. U1 only
  ships the schema additions that make the layout possible; the
  filesystem move + manufacturer entries land in C22 U2/U3/U6.

### CLI (forward-pointer)
- `dbf migrate` (new): v1.1 → v1.2 transformation. Adds `aliases: []`,
  populates `manufacturer_slug` from a `vendor_map`, optional
  `--nest-by-manufacturer` flag for filesystem migration. Lands in
  C22 U6.
- `dbf validate`: cross-file alias collision check (rejects two boards
  or manufacturers sharing an alias case-insensitive +
  whitespace-collapsed). Lands in C22 U4.
- `dbf validate`: `meta.confidence_skipped` ↔ `meta.confidence` mutual
  exclusion. Lands in C22 U5.
- `dbf validate`: `manufacturer_slug` ↔ `manufacturers/<slug>.yaml` link
  + canonical_name match. Lands in C22 U5.

### Tests
- `cli/tests/test_v12_back_compat.py` — every existing v1.1 board
  re-validates against the v1.2 schema (the additive-only iron rule).
- `cli/tests/test_v12_features.py` — positive + negative cases for
  each new field.
- `spec/tests/examples/v1.2-features.ubds.yaml` — minimal valid board
  exercising every new field, used by the features test suite.

## v1.1.1 — 2026-04-12

Image tag simplification.

### Changed
- `metadata.image_tags` (array of enum strings) replaced with `metadata.top_view` (boolean).
  The image is either a top-down view or it isn't — the extra tag values (angle, sim-ready,
  pinout, block-diagram) were unused and added no value.

## v1.1.0 — 2026-04-08

Commerce separation. UBDS now describes only the board; pricing, vendors,
and affiliate data move to the devboardfinder `board_sellers` table and are
out of scope for this spec.

### Removed
- Top-level `pricing` block in its entirety, including `msrp_usd`, `vendors`,
  per-vendor `price_usd`, `in_stock`, and `affiliate_url` fields.
- Any YAML containing a top-level `pricing:` key is now rejected by schema
  validation (enforced via a top-level `not: { required: [pricing] }`).

### Added
- `meta.product_url` — **required** string (`format: uri`) pointing at the
  canonical manufacturer product page (e.g. `raspberrypi.com`,
  `developer.nvidia.com`, `espressif.com`). Must not be a reseller,
  distributor, affiliate landing page, or marketplace listing.

### Migration for contributors
1. Delete the entire `pricing:` block from your `.ubds.yaml` file.
2. Add `meta.product_url:` pointing at the manufacturer's own product page.
3. Bump `ubds_version` from `"1.0"` to `"1.1"`.
4. Re-run `pytest spec/tests/` (or `dbf validate`) to confirm the board
   still validates against the updated schema.

## v1.0.0 — 2026-04-07

Initial release.

- `ubds-v1.schema.json` — Draft-07 JSON Schema covering identity, processing
  elements, interfaces, wireless, software, physical, pricing, metadata, and
  provenance metadata.
- `ubds-v1.reference.ubds.yaml` — annotated reference doc (NVIDIA Jetson Orin
  Nano Developer Kit) documenting every field with inline comments.
- Required top-level fields: `ubds_version`, `name`, `slug`, `manufacturer`,
  `board_type`, `meta` (with at least one source URL).
- Closed enums on `board_type`, `status`, `difficulty_level`, `ecosystem_size`,
  `meta.data_completeness`, `meta.confidence.*`, `metadata.image_tags`.
- Open extensibility (`additionalProperties: true`) on all structured objects.
