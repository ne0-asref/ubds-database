# Contributing to ubds-database

Welcome! This repository is the community-maintained directory of embedded
development boards, described in the
[Universal Board Description Standard (UBDS)](./spec/ubds-v1.schema.json).

Anyone can contribute a board — hobbyists, engineers, manufacturer reps, or
open-hardware designers. Every board that meets the ground rules below is
welcome, from a mainstream Arduino to a niche RISC-V prototype.

**Licensing note:** Code in `spec/` and `cli/` is Apache-2.0; board data in
`boards/` is CC-BY-4.0. By opening a PR you agree to license your
contribution under the applicable license.

---

## Quick start

1. **Fork** this repository.
2. Copy [`templates/minimal.ubds.yaml`](./templates/minimal.ubds.yaml) to
   `boards/<your-board-slug>.ubds.yaml`.
3. Fill in every field — the template has comments explaining each one.
4. Run `dbf validate boards/<your-board-slug>.ubds.yaml` to check your file
   (install the CLI with `pip install ./cli`).
5. Open a pull request using the **Board Submission** template.

That's it for most boards. If your board has many features (multiple radios,
complex power tree, etc.), start from
[`templates/full.ubds.yaml`](./templates/full.ubds.yaml) instead. For the
exhaustive field reference, see
[`spec/ubds-v1.reference.ubds.yaml`](./spec/ubds-v1.reference.ubds.yaml).

---

## Adding a board image

A good product photo makes a board entry dramatically more useful. Images
are optional — a board without images is still accepted — but submitting
one (or a few) is one of the highest-impact things a contributor can do.

### Directory layout

Images live under `images/<slug>/`, where `<slug>` matches the board
YAML's `slug:` field **exactly**. All lowercase, hyphens only. For a
board with `slug: rp2040-pico`, the image directory is
`images/rp2040-pico/`.

### Canonical filenames

Use these five filenames — no others, no suffixes, no versions:

| Filename | Role | Background |
|---|---|---|
| `top-view.png` | Primary product photo — strongly preferred | transparent |
| `pinout.png` | Distinct asset — pinout diagram | opaque OK |
| `angle.png` | Fallback for top-view | transparent |
| `bottom-view.png` | Fallback for top-view | transparent |
| `block-diagram.png` | Fallback for top-view | opaque OK |

### Prefer `top-view.png`

The frontend's primary-image slot has a fallback chain: it shows
`top-view.png` when present, otherwise one of `angle.png`,
`bottom-view.png`, or `block-diagram.png`. In other words, we **prefer
`top-view.png`** — a clean top-down product photo is the first-choice
contribution. The fallbacks exist only for boards where a top-down shot
isn't available (e.g., a SoM whose useful geometry is on the underside,
or a module where the block diagram is more informative than a photo).

### Pinout is distinct

`pinout.png` is a **distinct asset** and has **no fallback chain**. It
ships in its own slot on the board page. A pinout diagram is never a
substitute for `top-view.png`, and vice versa. Contribute either or both
— they do not compete.

### Format rules

- **PNG only.** No `.jpg`, `.webp`, or `.svg`.
- **1 MB per file, max.** Compress with `pngquant`, `oxipng`, or the
  "Save for web" option of your editor. If your source PNG is larger,
  shrink it before committing.
- **RGBA for photos** (`top-view.png`, `bottom-view.png`, `angle.png`) —
  transparent background so the board composites cleanly on any theme.
- **Opaque is OK for diagrams** (`pinout.png`, `block-diagram.png`) —
  these are line art on a flat background and don't need transparency.
- **No filename suffixes or versions.** `top-view-v2.png`,
  `top-view_final.png`, `top-view@2x.png` are all rejected.

### Capture guidance

For photographs, a few minutes of setup produces dramatically better
results than a phone snap:

- **Top-down, square to the board.** Keep the camera plane parallel to
  the PCB to avoid keystoning. A phone clamped to a cheap copy stand
  works well.
- **Flat, diffuse lighting.** No harsh shadows. Window light through a
  thin curtain, or two soft LED panels at 45°, is ideal.
- **Even focus edge to edge.** Stop down (small aperture) if you have
  manual control — depth of field matters on tall components.
- **Background removal.** Shoot against white paper, then remove the
  background. Tools that work:
  - **GIMP** — Fuzzy Select + Layer → Transparency → Add Alpha Channel.
  - **remove.bg** — web/CLI service, one-click.
  - **ImageMagick** — for simple cases,
    `magick in.png -fuzz 5% -transparent white out.png`.

### License

Self-photographed images must be licensed under
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). Manufacturer
press-kit material is welcome **if** its license is CC-BY-4.0-compatible
(CC-BY, CC0, or a permissive manufacturer media license). Attribute
every image in the board YAML's `meta.sources[]` with the source URL.

### Recommended flow

The `dbf` CLI takes care of placement, validation, and filename
normalization:

```
dbf add-image <slug> path/to/img.png --as top-view
```

It verifies the PNG signature, checks that the file is ≤ 1 MB, writes
it to `images/<slug>/top-view.png`, and confirms the `<slug>` matches a
real board file. See `dbf add-image --help` for the full option list.

### Pre-PR check

Before opening a pull request, run the image-aware validator:

```
dbf validate boards/ --check-images
```

This runs the normal schema/validator pass and additionally verifies
every image referenced by (or colocated with) a board entry — filename,
size, PNG signature, pixel format. Paste the output into your PR.

---

## Ground rules

- **Commercially available or open hardware.** The board must be purchasable
  today, or its design files must be published under an open-hardware license.
  No vaporware, unreleased prototypes, or crowdfunding-only projects.

- **`meta.product_url` required.** Must point to the manufacturer's own
  product page — not a reseller, distributor, or affiliate link.

- **`meta.sources[]` required.** At least one verifiable public URL (datasheet,
  official docs, or manufacturer page) used to compile the data.

- **Must pass `dbf validate`.** Run `dbf validate boards/<slug>.ubds.yaml`
  before submitting. Paste the output into your PR.

- **Indie and open-hardware boards are first-class citizens.** A board from a
  solo maker with published KiCad files is just as welcome as one from a
  major manufacturer.

- **No commercial content.** No affiliate links, promotional URLs, referral
  codes, or marketing copy anywhere in your YAML file. The only exception is
  `meta.product_url`, which must point to the manufacturer's own page.

---

## Templates

| Template | When to use | Lines |
|----------|------------|-------|
| [`templates/minimal.ubds.yaml`](./templates/minimal.ubds.yaml) | Most boards — required fields only | ~80 |
| [`templates/full.ubds.yaml`](./templates/full.ubds.yaml) | Feature-rich boards — all common sections | ~200 |
| [`spec/ubds-v1.reference.ubds.yaml`](./spec/ubds-v1.reference.ubds.yaml) | Exhaustive reference (Jetson Orin Nano) | ~960 |

Start with **minimal**. You can always add sections later.

---

## Per-section confidence standard

Contributors mark their confidence for each major section in
`meta.confidence`. This helps reviewers prioritise verification effort.

| Level | Meaning | Source examples |
|-------|---------|-----------------|
| **high** | Copied directly from official datasheet or verified on physical hardware | Datasheet PDF, hands-on measurement, manufacturer spec table |
| **medium** | Cross-referenced multiple sources but not independently verified | Product page + community wiki, multiple retailer listings agreeing |
| **low** | Best guess from limited information; needs verification | Single blog post, marketing material, inferred from similar board |

Set a confidence level for each section you fill in: `processing`, `interfaces`,
`wireless`, `software`, `power`, `getting_started`. Leave out sections you
didn't fill in.

---

## Badge tiers

Boards earn badges based on data quality:

| Badge | Appearance | How to earn |
|-------|-----------|-------------|
| *(none)* | No badge | Default state for new submissions |
| **community** | Green outline | Board data reviewed and confirmed by at least one other contributor (`meta.community_reviewed: true`) |
| **verified** | Blue filled | Data verified against official sources by a maintainer (`meta.verified: true`) |

Badges are earned through review, not self-assigned. Set
`meta.community_reviewed` and `meta.verified` to `false` in your submission —
a maintainer or reviewer will update them.

---

## PR governance

Pull requests are reviewed under a two-tier system:

- **Pipeline PRs** — automated imports where all sections have
  `confidence: high` may be auto-merged after CI passes.
- **Community PRs** — contributions from the community require at least one
  human review before merging.
- **Verified-board changes** — any PR that modifies a board with
  `meta.verified: true` requires human review, regardless of source.
- **Low-completeness stubs** — boards below 50% `data_completeness` require
  human review to confirm the board meets the ground rules.

---

## Code of conduct

Be kind, constructive, and welcoming. We follow the
[Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
If you experience or witness unacceptable behaviour, open an issue or contact
the maintainers directly.
