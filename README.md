# PRISM2: life cycle inventory as code

PRISM2 turns process simulations and plant data into **checked, parameterised, certified life cycle
inventories** that XYCLE can import. It is the PRISM module of the Innovate UK project 10201112
(*Process-Integrated Sustainability Modelling for Advanced Materials LCI Generation*), rebuilt on the
[ChemE-as-Code](https://github.com/ChemE-as-Code) approach: **a model is a folder of plain files in git**,
a command line checks it and reports every problem at a `file:line`, coding agents work on it under
written rules, and a viewer shows the result.

> Research software. The process types are drafts, the example data is synthetic, and nothing has been
> imported into a live XYCLE workspace yet. See [docs/STATUS.md](docs/STATUS.md).

## The idea in one sentence

Bring a process model or real operating data; PRISM2 checks it, fits and tests a model across the
operating window and feedstock grades, certifies it (fail closed), and hands XYCLE an inventory with its
ranges, quality tier and evidence. **PRISM2 never calculates impacts**: background data and
characterisation stay in XYCLE.

## Quick start

```bash
pip install -e '.[dev]'
cd examples/leach-demo
prism validate                 # findings by file:line with stable ids
prism build --demo             # fit + benchmark, certify, inventory, method note -> build/
prism status                   # the verdict card; is build/ up to date?
prism export xycle --demo      # Parameter Import .csv, Model Import .xlsx, draft DPP block
cd ../.. && prism serve examples   # viewer at http://127.0.0.1:8765
```

Start a new model with `prism init my-model --process-type bml-v1`; it includes agent skills
(`.claude/skills/`, `AGENTS.md`).

## A model repository

| File | What it holds | Journey stage |
|---|---|---|
| `scope.yaml` | goal, functional unit, boundary, intended use, target tier, who agreed it | 1 Frame |
| `prism.yaml` | process type, data origin and tool version, excluded runs with reasons, model and gate settings | 2-3 |
| `feedstocks.yaml` | low, mid and high grades; the operating point; input uncertainty | 3, 8 |
| `data/runs.csv` | one row per run: conditions, feedstock, outputs, optional assays | 3 |
| `signoffs.yaml` | technical, independent and LCA sign-offs | 7 |
| `decisions/*.md` | decision records (e.g. the model-selection rule, written before fitting) | all |
| `build/` | generated: findings, model, certification, inventory, method note, lock file | 4-9 |

Process types (fields, windows, rules, recipe) live in the **process library**
(`src/prism2/library/*.yaml`) as reviewed configuration. Adding the rare earth module is a new file,
not new code.

## What it does, stage by stage

| Stage | Command | What happens |
|---|---|---|
| Check | `prism validate` | schema and consistency of every file; seven rules on every run (composition closure, window, acid stoichiometry, reductant, pulp density, output bounds, element balance). A rule that cannot run says **skipped**, never pass. |
| Design runs | `prism design` | Sobol or Latin hypercube run sheet over the window per grade; coverage of existing runs |
| Parameterise | `prism build` | polynomial, neural network and Gaussian process fitted on **one** 80/20 split; 5-fold CV, Shapiro-Wilk on residuals, Sobol sensitivity, applicability domain; the family is chosen by a rule written first |
| Certify | `prism build` | accuracy gate (held-out R² ≥ 0.92, p90 relative error, residual normality, held-out count); quality tier A-D from data origin, review status, coverage and sign-offs; export blockers |
| Inventory | `prism build` | exchanges per functional unit for each grade, Monte Carlo p5/p50/p95, the input driving each exchange, the grade envelope |
| Report | `prism build` | auto-drafted method note (O11) with scope, data, model statistics, inventory, tier, assumptions and input hashes |
| Hand over | `prism export xycle` | Parameter Import and Model Import to the written importer rules; draft DPP block. Refused if the build is outdated or any blocker stands; `--demo` watermarks |
| Maintain | `prism status` | input hashes in `build/prism.lock.json` flag outdated results |

The verdict card answers four questions in plain words (usable? covers the range? balances? model
accurate?) and gives one next action, as in the PRISM guided path (Spec 6).

## Documentation

- [docs/FILE-FORMATS.md](docs/FILE-FORMATS.md): every file and its keys
- [docs/CHEME-AS-CODE.md](docs/CHEME-AS-CODE.md): what was taken from ChemE-as-Code and what PRISM2 adds
- [docs/ROADMAP.md](docs/ROADMAP.md): mapping to work packages, milestones and backlog IDs
- [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md): engineering assumptions awaiting review
- [docs/STATUS.md](docs/STATUS.md): what is verified and what is not
- [AGENTS.md](AGENTS.md): rules for coding agents working on this repository

## Licence

Not yet chosen. ChemE-as-Code is AGPL-3.0; PRISM2 shares no code with it (only the approach), so the
licence is Minviro's decision. Do not publish until it is set.
