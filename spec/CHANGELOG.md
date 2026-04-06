# UBDS Spec Changelog

## v1.0 — 2026-04-06

Initial release of the Universal Board Description Standard.

- 20 top-level sections covering hardware, software, and ecosystem
- JSON Schema (Draft 2020-12) for validation
- Extensible: unknown fields allowed at every level
- Required fields: `ubds_version`, `name`, `slug`, `manufacturer`, `board_type`
- Per-section confidence levels (`high` / `medium` / `low`) for data provenance
- Support levels for software entries (`board` / `controller` / `community` / `experimental` / `not_supported`)
- Heterogeneous compute support (multiple processing elements per board)
- Three-tier learning resources (board / controller / core)
- Board variant tracking via `parent_board` reference
