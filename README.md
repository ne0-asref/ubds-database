# ubds-database

Open-source directory of embedded development boards, described in the
**Universal Board Description Standard (UBDS)**.

This repository holds three things:

- **`spec/`** — the UBDS JSON Schema (v1.1). Start at
  [`spec/ubds-v1.schema.json`](./spec/ubds-v1.schema.json).
- **`boards/`** — one `*.ubds.yaml` file per board, validated against the
  schema by CI on every push and pull request.
- **`cli/`** — `dbf`, a small Python CLI for validating, searching, and
  importing UBDS files. Install with `pip install ./cli`.

## License

Dual-licensed. Code (`spec/`, `cli/`) under Apache-2.0; board data
(`boards/`) under CC-BY-4.0. See [`LICENSE`](./LICENSE),
[`LICENSE-CODE`](./LICENSE-CODE), and [`LICENSE-DATA`](./LICENSE-DATA).

## Contributing

Contributor documentation (how to add a board, PR template, review flow)
lands in a follow-up component. For now, open an issue if you want to
propose a board and we'll sort out the mechanics together.
