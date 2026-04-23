# C21.2 fixture tree

Synthetic ubds-database-shaped tree driving `test_validate_images.py`
Tier 2 integration cases. YAMLs are checked in; PNGs are generated on
demand by the `make_fixture_pngs` fixture in `cli/tests/conftest.py` so
the repo stays binary-free.

Expected counts when `check_images()` runs against this tree:

| Severity | Count | Source                                                                 |
| -------- | ----- | ---------------------------------------------------------------------- |
| error    | 5     | Rule 5 (pins.png), Rule 7 (oversize), Rule 11 (url-mismatch), Rule 13a (duplicated collision), Rule 13b (something-else mismatch) |
| warn     | 2     | Rule 9 (deleted-board orphan), Rule 10 (fallback-only)                 |

`clean-board.ubds.yaml` alone is schema-valid so the single-file
invocation test can exit 0 without image checks. The other YAMLs are
minimal stubs — `check_images` only reads `slug` and `meta.*`, not the
full schema.

Slug collision + mismatch are folded onto two files by design:
`duplicated.ubds.yaml` (self-matching) and `something-else.ubds.yaml`
(slug=duplicated, mismatches own filename AND collides). That single
pair produces exactly 1 duplicate error + 1 mismatch error = 2 slug
errors, matching the test-matrix §2.2.3 budget.
