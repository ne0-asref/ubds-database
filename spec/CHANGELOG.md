# UBDS Changelog

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
