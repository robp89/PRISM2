---
name: prism-model
description: Work on a PRISM2 model repository - fix validation findings, add runs, build, read the verdict and export to XYCLE. Use when the folder has a prism.yaml.
---

# PRISM2 model repository

1. Run `prism validate --json`. Group findings by `id`. Errors block; warnings are reported.
2. For each error, open the file at `where` and fix the data or the file. If the fix would change a
   window, rule or recipe in a process type, stop: write `decisions/D-NNN-*.md` instead.
3. Data that is wrong and cannot be fixed (a bad assay, a logged typo awaiting the run sheet): add it to
   `data.exclude` in `prism.yaml` with the reason. Never delete rows.
4. `prism build` (add `--demo` only for synthetic data). Read the verdict: level, four questions, blockers.
5. If the model fails its gate, look at `build/model.json` coverage and Sobol indices, then use
   `prism design` to propose runs where the model is weakest. Do not loosen the gate.
6. Report: the verdict, the tier and what raises it, excluded runs, and the next action.
