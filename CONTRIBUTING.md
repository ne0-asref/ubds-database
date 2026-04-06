# Contributing to UBDS Database

Thanks for helping build the most comprehensive dev board directory on the internet. Whether you're adding a board you just bought, fixing a typo in an existing entry, or representing a manufacturer — this guide covers everything you need.

## Ground Rules

- **Commercially available boards only.** The board must be purchasable or be open hardware with published design files. No vaporware, unreleased prototypes, or crowdfunding-only boards.
- **Sources required.** Every board file must include at least one verifiable public URL in `meta.sources[]`. Datasheets, manufacturer pages, and distributor listings all count.
- **Must pass validation.** Run `dbf validate` before opening a PR. The CI will reject files that don't pass the JSON Schema.
- **Indie and open hardware boards are first-class citizens.** A $5 RISC-V board deserves the same quality entry as a $500 SBC.

## Quick Start

### 1. Fork and clone

```bash
gh repo fork ne0-asref/ubds-database --clone
cd ubds-database
```

### 2. Pick a template

| Template | Lines | When to use |
|----------|-------|-------------|
| [`templates/minimal.ubds.yaml`](templates/minimal.ubds.yaml) | ~45 | **Start here.** Covers required fields + processing + software. Good for 80% of contributions. |
| [`templates/full.ubds.yaml`](templates/full.ubds.yaml) | ~230 | All commonly-used sections with comments. Use when you have detailed specs. |
| [`templates/reference.ubds.yaml`](templates/reference.ubds.yaml) | ~500 | Fully-populated Jetson Orin Nano showing every field. Reference only — don't copy this as a starting point. |

### 3. Create your board file

```bash
cp templates/minimal.ubds.yaml boards/your-board-slug.ubds.yaml
```

The filename must match the `slug` field inside the YAML. Slugs are lowercase, hyphens only (e.g., `esp32-s3-devkitc-1`).

### 4. Fill in the data

Open the file and replace placeholder values with real data. Key things to get right:

- **`name`** — the official product name as the manufacturer uses it
- **`slug`** — unique, lowercase, hyphens only
- **`manufacturer`** — company name, not abbreviation
- **`board_type`** — at least one: MCU, SBC, SoM, Carrier, FPGA, etc.
- **`processing`** — at least one element with `role: primary`
- **`meta.sources`** — at least one URL where you got the data

### 5. Validate locally

```bash
pip install -e cli/
dbf validate boards/your-board-slug.ubds.yaml
```

Fix any errors. The `--fix` flag can auto-correct common issues:

```bash
dbf validate --fix boards/your-board-slug.ubds.yaml
```

### 6. Open a pull request

```bash
git checkout -b add/your-board-slug
git add boards/your-board-slug.ubds.yaml
git commit -m "feat(boards): add Your Board Name"
git push origin add/your-board-slug
```

Open a PR using the **Board Submission** template. Paste your `dbf validate` output in the PR description.

## Confidence Standard

Not all data is equally reliable. UBDS uses per-section confidence ratings so reviewers know where to focus verification.

Mark confidence in the `meta.confidence` block:

```yaml
meta:
  confidence:
    processing: high
    interfaces: high
    wireless: medium
    software: medium
    power: low
    pricing: medium
```

| Level | Meaning | Source examples |
|-------|---------|----------------|
| **high** | Verified against primary source | Official datasheet, manufacturer page, hands-on testing |
| **medium** | Likely correct, secondary source | Distributor listing, community wiki, tutorial blog |
| **low** | Best guess, unverified | Forum post, personal estimate, inferred from similar board |

Sections not present in the board file don't need a confidence entry. All confidence fields default to `medium` if omitted.

**Tip:** It's better to submit with `confidence: low` on a section than to leave the section out entirely. Low-confidence data is still useful — it just gets flagged for verification.

## Badge Tiers

Every board on DevBoardFinder earns a badge based on how its data was verified:

| Badge | Label | How earned |
|-------|-------|------------|
| — | Unverified | Default state. Pipeline auto-merge or initial submission. |
| Green outline | **Community-reviewed** | PR reviewed and approved by a maintainer. Sets `community_reviewed: true`. |
| Blue filled | **Manufacturer-verified** | Manufacturer submits or confirms data using a domain email + maintainer approves. Sets `verified: true`. |

### For manufacturers

If you represent a board manufacturer and want the **verified** badge:

1. Open a PR from an account associated with your company domain email
2. Set `data_completeness: full` — fill in all sections you have data for
3. A maintainer will verify your identity and approve

## PR Governance

| PR source | Review policy |
|-----------|--------------|
| Community member (new board) | Human review required |
| Community member (correction) | Human review required |
| AI pipeline (`confidence: high` on all fields) | Auto-merge eligible |
| Changes to `verified: true` boards | Human review required |
| Stub submissions (`data_completeness: stub`) | Human review required |

## Editing an Existing Board

1. Find the board file in `boards/`
2. Make your changes
3. Update `meta.last_verified` to today's date
4. Update `meta.sources` if you used a new source
5. Run `dbf validate` and open a PR

## Data Completeness

Set `meta.data_completeness` to reflect how much of the board is documented:

| Value | Meaning |
|-------|---------|
| **full** | All applicable sections filled in |
| **partial** | Required fields + some optional sections |
| **stub** | Only required fields (identity + one processing element) |

## File Structure

```
boards/
  esp32-s3-devkitc-1.ubds.yaml     # one file per board
  raspberry-pi-5.ubds.yaml
  your-new-board.ubds.yaml
```

Board images go in the separate [ubds-images](https://github.com/ne0-asref/ubds-images) repo:

```
images/{slug}/top-view.png          # required for site rendering
images/{slug}/angle.png             # optional
```

## Common Mistakes

- **Wrong slug format** — must be lowercase, hyphens only, no underscores or spaces. Pattern: `^[a-z0-9][a-z0-9-]*[a-z0-9]$`
- **Missing `meta.sources`** — every board needs at least one verifiable URL
- **Filename doesn't match slug** — `boards/my-board.ubds.yaml` must contain `slug: "my-board"`
- **Forgetting `ubds_version: "1.0"`** — required first field in every file

## Getting Help

- Open an issue if you're unsure about a field
- Check `templates/reference.ubds.yaml` for a fully-worked example
- Run `dbf validate --fix` to auto-correct common issues
