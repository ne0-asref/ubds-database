<!--
Thanks for contributing to ubds-database! This template is the default PR
form. For the guided board-submission template, append `?template=board-submission.md`
to the PR URL. New to the project? Start with CONTRIBUTING.md.
-->

## Summary

<!-- One or two sentences — what does this change? -->

## Commit-prefix guide

Keep commit messages in the shape `type(scope): message` so the diff
intent is obvious to reviewers at a glance:

- `feat(boards): add <board-slug>` — net-new board entry under `boards/`
- `fix(boards): <board-slug> <what changed>` — correction to an existing board
- `feat(images): <board-slug> add <role>` — new image asset under `images/<slug>/`
- `fix(images): <board-slug> <what changed>` — replace/retouch an image
- `feat(spec): <change>` — UBDS schema change (additive only; see SPEC.md)
- `feat(cli): <change>` — `dbf` CLI change
- `fix(cli): <change>` — CLI bug fix
- `docs(...)`, `test(...)`, `chore(...)` — everything else

## Checklist

- [ ] `dbf validate boards/ --check-images` runs locally and passes
- [ ] Slug in YAML matches the board filename (`boards/<slug>.ubds.yaml`)
- [ ] If images are included, they live under `images/<slug>/` using the
      canonical filenames — `top-view.png`, `pinout.png`, `angle.png`,
      `bottom-view.png`, `block-diagram.png` (no suffixes or versions)
- [ ] Every PNG is ≤ 1 MB and uses the correct color mode
      (RGBA for photos; opaque OK for `pinout.png` / `block-diagram.png`)
- [ ] `meta.product_url` points at the manufacturer's own page
- [ ] `meta.sources[]` cites at least one verifiable public URL
- [ ] Confidence levels set for every filled-in section
- [ ] No affiliate links, referral codes, or marketing copy

## Sources & license

<!-- List the sources you used (datasheets, product pages, press kits). -->

By submitting this PR I agree that:

- Code changes (`spec/`, `cli/`, workflows) are contributed under **Apache-2.0**.
- Board-data changes (`boards/`) are contributed under **CC-BY-4.0**.
- Any image I upload is self-photographed and **CC-BY-4.0** licensed, OR
  is manufacturer press-kit material whose license is CC-BY-4.0-compatible.
  Attribution for each image appears in `meta.sources[]` of the board YAML.

## Validation output

<details>
<summary><code>dbf validate boards/ --check-images</code></summary>

```
paste output here
```

</details>

---

New contributor? The full image-contribution workflow, capture guidance,
and the `dbf add-image` helper live in
[CONTRIBUTING.md §Adding a board image](CONTRIBUTING.md#adding-a-board-image).
