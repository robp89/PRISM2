# File formats

## prism.yaml (schema `prism2/project/v1`)

| Key | Meaning |
|---|---|
| `id`, `title` | identifiers |
| `process_type` | library id (`bml-v1`) or a path to a local process-type file |
| `data.runs` | path to the run table |
| `data.origin` | `plant`, `pilot`, `lab`, `simulation`, `literature` or `synthetic`. Decides the best reachable tier |
| `data.tool` | `{name, version}` of the simulator or script (warning if missing for simulation) |
| `data.validation` | `{status: compared, against, within_tolerance}`: simulation checked against measurements (tier B) |
| `data.exclude` | `[{run, reason}]`: runs left out of the model. A reason is required |
| `model.targets` | outputs to model (default: all outputs of the process type) |
| `model.families` | any of `polynomial`, `ann`, `gp` |
| `model.degree` | polynomial degree (default 2) |
| `gate` | `min_runs` 20, `holdout_fraction` 0.2, `min_holdout_runs` 8, `min_r2` 0.92, `max_p90_rel_err_pct` 10, `min_normality_p` 0.05 |

## scope.yaml

`goal`, `functional_unit`, `boundary`, `intended_use` (`screening`, `internal_decision`, `customer_report`,
`regulatory_input`), `target_tier` (A-D), `lca_practitioner`, `agreed_by: {name, date}`. A cradle-to-gate
scope on a gate-to-gate process type is an error.

## feedstocks.yaml

`grades: {low: {...}, mid: {...}, high: {...}}` with composition fields (wt% of dry feed);
`operating_point: {...}` conditions for the inventory; `uncertainty: {composition_rel_sd, conditions_rel_sd}`.

## data/runs.csv

One row per run. Headers are the process type's field, output and assay keys plus `run_id` and `grade`.
Unknown columns are ignored with a warning; blank cells are "not supplied" (defaults apply to optional
fields). Findings point at the CSV line of the run.

## signoffs.yaml

`signoffs: [{role: technical|independent|lca, by, date, scope}]`. Tier A needs technical and independent;
tier B needs technical.

## Process type (schema `prism2/process-type/v1`)

| Key | Meaning |
|---|---|
| `status` | `draft`, `reviewed` (needs a `reviews:` record) or `retired`. Draft caps results at tier D |
| `functional_unit`, `boundary` | the unit process the recipe describes |
| `fields` | inputs: `group` (composition, conditions), `unit`, `min`, `max`, `default` or `required`, `element` |
| `outputs` | modelled outputs with bounds |
| `assays` | optional liquor and residue assays enabling the element balance |
| `rules` | `{id, check, title, params}`; checks: `composition_closure`, `operating_window`, `acid_stoichiometry`, `output_bounds`, `element_balance` |
| `constants` | `{value, provenance, source}` |
| `derived` | named formulas (names, numbers, `+ - * /`, parentheses, integer powers 0-4) |
| `exchanges` | `{key, name, category, unit, formula, assumption}`; one has `flow: reference`. Categories and units are those XYCLE accepts |

## build/ (generated, never edit)

`findings.json`, `rules.json`, `coverage.json`, `model.json` (all families, statistics, JSON weights),
`certification.json`, `verdict.json`, `inventory.json` and `inventory.csv` (per grade: value, p5, p50, p95,
driver), `method-note.md`, `prism.lock.json` (input SHA-256), and `xycle/` after export:
`parameter-import.csv` (Name, Formula, Unit, Description in dependency order), `model-import.xlsx`
(one sheet per grade; Process block then Outbound block with the ten XYCLE headers),
`dpp-draft.json` (`prism-dpp-draft-0.1`, `DRAFT_NOT_VALIDATED_AGAINST_ANY_STANDARD`). Demo exports carry `-DEMO`.
