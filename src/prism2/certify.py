"""Certification (fail closed), quality tiers A to D, and the plain-language verdict card.

Everything here is derived from evidence already stored in the model repository; nothing new is
claimed. Tier definitions follow the Simulation-to-LCI Review page 3 (proposed, docs/ASSUMPTIONS.md A-15).
"""
from __future__ import annotations

from .findings import Finding
from .project import MEASURED, Project

TIER_TEXT = {
    "A": "Measured data, reviewed process, accurate model, independent sign-off",
    "B": "Measured data, or simulation checked against measurements, with technical sign-off",
    "C": "Sound but unvalidated: simulation only, or not yet signed off",
    "D": "Screening only: draft process type, too few runs, or the model failed its gate",
}


def gate_checks(prj: Project, model: dict | None) -> dict:
    g = prj.gate
    if not model:
        return {"passed": False, "targets": {}, "reason": "no fitted model"}
    out, ok = {}, True
    for t, res in model["targets"].items():
        m = res["families"][res["chosen"]]["holdout"]
        checks = [
            {"id": "min_holdout_runs", "label": "Held-out runs", "value": m["n"], "limit": g["min_holdout_runs"], "pass": m["n"] >= g["min_holdout_runs"]},
            {"id": "min_r2", "label": "Held-out R²", "value": m["r2"], "limit": g["min_r2"], "pass": m["r2"] >= g["min_r2"]},
            {"id": "max_p90_rel_err_pct", "label": "90th percentile relative error %", "value": m["p90_rel_err_pct"], "limit": g["max_p90_rel_err_pct"], "pass": m["p90_rel_err_pct"] <= g["max_p90_rel_err_pct"]},
            {"id": "min_normality_p", "label": "Residual normality p", "value": m["normality_p"], "limit": g["min_normality_p"], "pass": not (m["normality_p"] < g["min_normality_p"])},
        ]
        passed = all(c["pass"] for c in checks)
        ok &= passed
        out[t] = {"family": res["chosen"], "checks": checks, "passed": passed}
    return {"passed": ok, "targets": out}


def signed(prj: Project, role: str) -> dict | None:
    return next((s for s in prj.signoffs if s.get("role") == role and s.get("by")), None)


def assess(prj: Project, findings: list[Finding], model: dict | None, cov: dict, demo: bool = False) -> dict:
    errors = [f for f in findings if f.severity == "error"]
    gate = gate_checks(prj, model)
    n = len(prj.runs)
    reasons: list[str] = []
    raise_by: list[str] = []

    # --- tier ---
    if not prj.process.reviewed:
        tier = "D"; reasons.append(f"process type {prj.process.id} is a draft")
        raise_by.append("have the process type reviewed by its named owners")
    elif n < prj.gate["min_runs"]:
        tier = "D"; reasons.append(f"{n} runs, fewer than the {prj.gate['min_runs']} needed for a model")
        raise_by.append("add runs (use `prism design` for a run sheet)")
    elif not gate["passed"]:
        tier = "D"; reasons.append("the fitted model failed its accuracy gate")
        raise_by.append("add runs where the model is weakest, or change model family")
    elif prj.origin in MEASURED:
        tier = "A" if cov.get("complete") else "B"
        if tier == "B":
            reasons.append("measured data does not cover the whole operating window")
            raise_by.append("add runs in the uncovered parts of the window")
    elif prj.origin == "simulation":
        v = (prj.data_spec.get("validation") or {})
        tier = "B" if v.get("status") == "compared" and v.get("within_tolerance") else "C"
        if tier == "C":
            reasons.append("simulation not yet compared with measurements")
            raise_by.append("compare against plant or published data (data.validation in prism.yaml)")
    else:
        tier = "C" if prj.origin == "literature" else "D"
        reasons.append(f"data origin: {prj.origin}")
    # sign-offs can only lower the tier
    if tier == "A" and not signed(prj, "independent"):
        tier = "B"; reasons.append("no independent sign-off"); raise_by.append("add an independent reviewer sign-off")
    if tier in ("A", "B") and not signed(prj, "technical"):
        tier = "C"; reasons.append("no technical sign-off"); raise_by.append("add a technical sign-off in signoffs.yaml")

    # --- export blockers (fail closed) ---
    blockers = []
    if errors:
        blockers.append(f"{len(errors)} validation error(s)")
    if not gate["passed"]:
        blockers.append("accuracy gate not passed" if model else "no fitted model")
    if prj.origin == "synthetic" and not demo:
        blockers.append("data is synthetic (demo mode only)")
    if not prj.process.reviewed and not demo:
        blockers.append("process type is a draft")
    certified = not blockers
    return {"tier": tier, "tier_text": TIER_TEXT[tier], "reasons": reasons, "raise_by": raise_by, "gate": gate,
            "blockers": blockers, "certified": certified, "demo": demo, "watermark": demo,
            "signoffs": prj.signoffs, "target_tier": (prj.scope or {}).get("target_tier")}


def verdict(prj: Project, findings: list[Finding], model: dict | None, cov: dict, cert: dict, rule_rows: list[dict]) -> dict:
    """The verdict card: a level, a headline, one next action and four questions."""
    errors = [f for f in findings if f.severity == "error"]
    n = len(prj.runs)
    q = []
    # 1 usable
    if not prj.runs:
        q.append({"q": "Is the data usable?", "a": "unknown", "why": "no runs yet", "fix": "add data/runs.csv or run `prism design`"})
    elif errors:
        q.append({"q": "Is the data usable?", "a": "no", "why": f"{len(errors)} error(s), first: {errors[0].message}", "fix": errors[0].fix or f"see {errors[0].where()}"})
    else:
        warn = [f for f in findings if f.severity == "warning"]
        q.append({"q": "Is the data usable?", "a": "caveats" if warn else "yes", "why": f"{n} runs read; {len(warn)} warning(s)", "fix": None})
    # 2 coverage
    if prj.runs:
        a = "yes" if cov["complete"] else "caveats" if cov["share"] >= 0.5 else "no"
        why = f"{cov['share'] * 100:.0f}% of the window covered" + (f"; gaps in {', '.join(cov['gaps'])}" if cov["gaps"] else "") + (f"; no runs for grade {', '.join(cov['missing_grades'])}" if cov["missing_grades"] else "")
        q.append({"q": "Does it cover the operating range?", "a": a, "why": why, "fix": None if a == "yes" else "generate a run sheet with `prism design`"})
    # 3 balance
    r7 = next((r for r in rule_rows if r["check"] == "element_balance"), None)
    if r7:
        a = {"pass": "yes", "warning": "caveats", "error": "no", "skipped": "unknown"}[r7["status"]]
        c = r7["counts"]
        q.append({"q": "Does it balance?", "a": a, "why": f"{c['pass']} runs close, {c['error']} fail, {c['skipped']} not checked", "fix": None if a == "yes" else "supply liquor and residue assays" if a == "unknown" else "check the failing runs"})
    # 4 model
    g = cert["gate"]
    if not model:
        q.append({"q": "Is the fitted model accurate?", "a": "unknown", "why": "no model built", "fix": "run `prism build`"})
    else:
        worst = min((c["value"] for t in g["targets"].values() for c in t["checks"] if c["id"] == "min_r2"), default=float("nan"))
        q.append({"q": "Is the fitted model accurate?", "a": "yes" if g["passed"] else "no", "why": f"lowest held-out R² {worst:.3f} (gate {prj.gate['min_r2']})", "fix": None if g["passed"] else "add runs or try another model family"})

    # level
    if not prj.runs:
        level, head, action = "Not started", "Bring run data or design the runs", "prism design"
    elif errors:
        level, head, action = "Needs fixing", "Fix the data before building", "prism validate"
    elif prj.origin == "synthetic":
        level, head, action = "Demo", "Invented data: shows the workflow, proves nothing", "replace with real runs"
    elif n < prj.gate["min_runs"]:
        level, head, action = "Screening only", f"{n} runs is a quick look, not a model", "add runs"
    elif not model:
        level, head, action = "Ready to build", "Data checks pass: build the model", "prism build"
    elif cert["tier"] in ("A", "B"):
        level, head, action = "Ready", f"Tier {cert['tier']} inventory ready for XYCLE", "prism export xycle"
    elif cert["tier"] == "C":
        level, head, action = "Use with care", "Sound inventory, not yet validated or signed off", cert["raise_by"][0] if cert["raise_by"] else "review"
    else:
        level, head, action = "Screening only", "Tier D: good for screening, not for claims", cert["raise_by"][0] if cert["raise_by"] else "review"
    return {"level": level, "headline": head, "next_action": action, "questions": q, "tier": cert["tier"]}
