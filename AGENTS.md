# AGENTS.md: working on the PRISM2 codebase

## Commands
- `pip install -e '.[dev]'` then `python -m pytest -q` (about a minute).
- `prism library check` checks every process type.
- `python scripts/generate_samples.py` regenerates the synthetic examples (never edit them by hand).
- `prism serve examples` runs the viewer (plain JS in `src/prism2/viewer/`, no build step).

## Non-negotiable rules
1. **Fail closed.** Never weaken a blocker, the gate, or the stale-build check to make an export pass.
2. **No invented science.** Windows, recipe coefficients, rule thresholds and gate defaults change only
   through a reviewed process-type file and an entry in `docs/ASSUMPTIONS.md` with a named reviewer
   (Irdanto S. L. for process data, Sahin A. for thermodynamics).
3. **No impacts in PRISM.** Physical flows only; XYCLE applies background data.
4. **No pickled models.** Models are JSON.
5. **Synthetic stays synthetic.** Example data is labelled `origin: synthetic` and every result from it is Demo.
6. **No customer or NDA data in git** (Altilium data goes to restricted storage).
7. Every check result is a `Finding` with a stable id and a `file:line`.

## Layout
`src/prism2/`: `project.py` (load and check a model repo), `library.py` + `library/*.yaml` (process types),
`rules.py` (run checks), `surrogate.py` (model families), `doe.py`, `certify.py` (gate, tier, verdict),
`inventory.py`, `build.py` (pipeline, export, snapshot), `exporters/`, `server.py`, `viewer/`, `cli.py`,
`templates/` and `skills/` (copied into new model repos by `prism init`).

## Definition of done
Tests pass, `prism library check` has no errors, docs updated (FILE-FORMATS, STATUS, ROADMAP as relevant),
and the commit references a backlog id from docs/ROADMAP.md.
