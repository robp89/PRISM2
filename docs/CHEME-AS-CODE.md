# PRISM2 and ChemE-as-Code

[ChemE-as-Code](https://github.com/ChemE-as-Code) (TU Delft Process Intelligence group) keeps a whole
chemical plant in git as linked engineering files (DEXPI P&IDs, YAML lists, Markdown decisions), checks
them with the `cheme` CLI, lets AI agents edit them under rules, and shows them in a browser viewer. Its
`cheme assess lca` derives an LCI dataset from a design flowsheet.

PRISM2 applies the same approach to a narrower and different job: **turning simulation runs and plant
data for battery recycling and critical-mineral routes into certified, parameterised inventories for
XYCLE.** It shares no code with ChemE-as-Code.

## Taken from ChemE-as-Code

| Idea | In ChemE-as-Code | In PRISM2 |
|---|---|---|
| The model is plain files in git | plant repository | model repository (`prism init`) |
| Findings by `file:line` with stable ids | `cheme validate` | `prism validate` (YAML line maps; CSV row lines) |
| Provenance on values | `provenance: assumed/given/calculated` with source | constants carry provenance and an assumption id; data carries origin and tool version |
| Flag outdated results | fingerprints on calculated values | input hashes in `build/prism.lock.json`; export refused when stale |
| Agent skills copied into each repo | `cheme init`, `cheme skills update` | `prism init`, `prism skills update` |
| Decisions in Markdown | `decisions/` | `decisions/` (e.g. the model-selection rule) |
| Read-only API and viewer | `cheme serve` + Vite viewer | `prism serve` + a dependency-free viewer in the XYCLE style |

## What PRISM2 adds for the PRISM goals

| PRISM need (grant plan) | ChemE-as-Code today | PRISM2 |
|---|---|---|
| Inventory across a **range** of feedstock quality (innovation 2) | one design case per flowsheet | low/mid/high grades, grade envelope, Monte Carlo p5-p95 per exchange |
| **Forward forecasting** for untested configurations (innovation 3, ANN-1) | none | polynomial, neural network and Gaussian process on identical held-out splits; decision rule written first; applicability-domain warnings |
| R² > 0.92 success criterion; MS3.2 gate | none | configurable accuracy gate, fail-closed certification |
| Many **runs** from simulators or plants, not one design | one balanced flowsheet | run tables, design of experiments, coverage check |
| Data quality you can defend to a customer | maturity and review status | quality tiers A-D from data origin, review, coverage and sign-offs; plain verdict card |
| XYCLE as the host platform (WP4) | its own LCA step | XYCLE Parameter Import and Model Import; no impacts calculated in PRISM |
| Method transparency for ISO 14040/44 reports | dataset metadata | auto-drafted method note with model statistics, tier, assumptions and input hashes |
| Battery passport inputs (DPP-1) | none | draft DPP block, labelled not validated |

## Where the two could meet

A ChemE-as-Code flowsheet (`process/flowsheet.yaml`, schema `cheme/process/v1`) carries stream flows and
compositions with provenance. A PRISM2 adapter that reads its streams into the PRISM run format would let a
plant designed in ChemE-as-Code feed PRISM2's model, certification and XYCLE export. That adapter is on the
roadmap (ADAPT-2), not built.
