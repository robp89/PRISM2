---
name: prism-process-type
description: Draft or change a PRISM2 process type (fields, windows, rules, recipe). Use for a new route such as REE refining or direct recycling.
---

# Process types are reviewed configuration

- A process type is one YAML file (schema `prism2/process-type/v1`). Copy the closest library type.
- New types start as `status: draft` with `placeholder: true` until real data and sources exist.
- Recipes use only names, numbers, `+ - * /`, parentheses and small integer powers, so XYCLE can import them.
- Every assumed constant gets `provenance: assumed` and an assumption id; add the assumption to
  `docs/ASSUMPTIONS.md` with who must review it.
- Exchange categories and units must be ones XYCLE accepts (see `prism library check`).
- Run `prism library check <file>` until there are no errors. Never set `status: reviewed` yourself:
  the named owners record their review under `reviews:`.
