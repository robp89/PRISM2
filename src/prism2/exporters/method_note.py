"""O11: an auto-drafted method note for the LCA report. A draft for the LCA practitioner to edit."""
from __future__ import annotations

from datetime import date

from ..project import ORIGINS, Project


def _fmt(x: float) -> str:
    return f"{x:.4g}"


def render(prj: Project, model: dict | None, inventory: dict, cert: dict, cov: dict, hashes: dict) -> str:
    pt, s = prj.process, prj.scope or {}
    L = [f"# Method note: {prj.title}", "",
         f"_Drafted by PRISM2 on {date.today().isoformat()} from the files in this repository. A draft for the LCA practitioner to review; it states only what the repository records._", ""]
    if cert["demo"] or prj.origin == "synthetic":
        L += ["> **Demonstration.** The data is synthetic or the process type is unreviewed. Nothing here is evidence.", ""]
    L += ["## Goal and scope", "",
          f"- **Goal:** {s.get('goal', 'not stated')}",
          f"- **Functional unit:** {s.get('functional_unit', 'not stated')}",
          f"- **System boundary:** {s.get('boundary', 'not stated')} (process type: {pt.data.get('boundary', '')})",
          f"- **Intended use:** {s.get('intended_use', 'not stated')}; target tier {s.get('target_tier', '-')}",
          f"- **Agreed by:** {(s.get('agreed_by') or {}).get('name', 'not yet agreed')}", "",
          "## Process and data", "",
          f"- **Process type:** {pt.title} (`{pt.id}` v{pt.data.get('version')}), status **{pt.status}**.",
          f"- **Data origin:** {prj.origin}: {ORIGINS.get(prj.origin, '')}. {len(prj.runs)} runs.",
          f"- **Coverage of the operating window:** {cov['share'] * 100:.0f}%" + (f"; gaps in {', '.join(cov['gaps'])}" if cov["gaps"] else "") + ".", ""]
    if model:
        L += ["## Fitted models", "",
              f"{model['n_train']} runs trained, {model['n_holdout']} held out before fitting (seed {model['seed']}). Families compared on the same split: {', '.join(model['families'])}. Decision rule: {model['decision_rule']}", "",
              "| Output | Chosen | Held-out R² | p90 rel. error % | Residual normality p | Gate |", "|---|---|---|---|---|---|"]
        for t, r in model["targets"].items():
            m = r["families"][r["chosen"]]["holdout"]
            ok = cert["gate"]["targets"].get(t, {}).get("passed")
            L.append(f"| {t} | {r['chosen']} | {m['r2']:.3f} | {m['p90_rel_err_pct']:.1f} | {m['normality_p']:.3f} | {'pass' if ok else 'fail'} |")
        L.append("")
    L += ["## Inventory", "", f"Per {inventory['functional_unit'].get('amount')} {inventory['functional_unit'].get('unit')} {inventory['functional_unit'].get('of')}. Ranges are 5th to 95th percentiles of a {inventory['n_mc']}-sample Monte Carlo (composition ±{inventory['uncertainty']['composition_rel_sd'] * 100:.0f}%, conditions ±{inventory['uncertainty']['conditions_rel_sd'] * 100:.0f}% relative s.d., model error from held-out RMSE).", ""]
    grades = list(inventory["grades"])
    L += ["| Exchange | Unit | " + " | ".join(grades) + " |", "|---|---|" + "---|" * len(grades)]
    for ex in pt.exchanges:
        cells = [f"{_fmt(inventory['grades'][g]['exchanges'][ex['key']]['value'])} ({_fmt(inventory['grades'][g]['exchanges'][ex['key']]['p5'])} to {_fmt(inventory['grades'][g]['exchanges'][ex['key']]['p95'])})" for g in grades]
        L.append(f"| {ex['name']} | {ex['unit']} | " + " | ".join(cells) + " |")
    L += ["", "No emission factors are applied in PRISM. Background data and impact assessment are done in XYCLE.", "",
          "## Quality", "", f"- **Tier {cert['tier']}:** {cert['tier_text']}."]
    L += [f"- {r}" for r in cert["reasons"]]
    if cert["raise_by"]:
        L += ["- **To raise the tier:** " + "; ".join(cert["raise_by"]) + "."]
    L += ["", "## Assumptions", ""]
    seen = sorted({ex.get("assumption") for ex in pt.exchanges if ex.get("assumption")})
    L += [f"- {a} (see docs/ASSUMPTIONS.md)" for a in seen] or ["- none recorded"]
    L += ["", "## Reproducibility", "", "| File | SHA-256 |", "|---|---|"] + [f"| {k} | `{v[:16]}…` |" for k, v in hashes.items()]
    return "\n".join(L) + "\n"
