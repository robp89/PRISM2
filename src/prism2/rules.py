"""The validation rules. Each rule is configured in the process type and evaluated on every run.

A rule that cannot run (missing fields) reports ``skipped``, never ``pass``.
"""
from __future__ import annotations

import math

from .chem import ATOMIC_WEIGHTS
from .findings import Finding
from .library import ProcessType


def _num(run: dict, key: str) -> float | None:
    v = run.get(key)
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _with_defaults(pt: ProcessType, run: dict) -> dict:
    full = dict(pt.defaults())
    full.update({k: v for k, v in run.items() if v not in (None, "")})
    return full


def check_run(pt: ProcessType, run: dict, *, file: str | None = None, line: int | None = None,
              run_id: str | None = None) -> list[Finding]:
    """All rule results for one run (one finding per rule, plus extra findings for multiple failures)."""
    r = _with_defaults(pt, run)
    out: list[Finding] = []
    for rule in pt.rules:
        rid, check, params = rule["id"], rule["check"], rule.get("params", {}) or {}
        fid = f"{rid}.{check.replace('_', '-')}"
        res = _RULES[check](pt, r, params)
        for sev, msg, fix in res:
            out.append(Finding(fid, sev, msg, file, line, fix, subject=run_id, data={"rule": rid, "title": rule.get("title")}))
    return out


def _composition_closure(pt, r, p):
    keys = pt.composition_fields()
    vals = [_num(r, k) for k in keys]
    if any(v is None for k, v in zip(keys, vals) if pt.fields[k].get("required")):
        return [("skipped", "composition incomplete, closure not checked", "supply all required composition fields")]
    total = sum(v for v in vals if v is not None)
    limit = float(p.get("max_sum_pct", 100.5))
    if total > limit:
        return [("error", f"composition sums to {total:.2f} wt% (limit {limit})", "check the assay basis: wt% of dry feed")]
    return [("pass", f"composition sums to {total:.2f} wt%", None)]


def _operating_window(pt, r, p):
    res = []
    for k in p.get("fields", []):
        spec = pt.fields.get(k, {})
        v = _num(r, k)
        if v is None:
            if spec.get("required"):
                res.append(("error", f"{k} is required but missing", f"add a {k} column"))
            else:
                res.append(("skipped", f"{k} not supplied", None))
            continue
        lo, hi = float(spec.get("min", -math.inf)), float(spec.get("max", math.inf))
        if not lo <= v <= hi:
            res.append(("error", f"{k} = {v:g} {spec.get('unit', '')} is outside the window {lo:g} to {hi:g}",
                        "correct the value, or widen the window in a reviewed process type"))
    if not res:
        res.append(("pass", "inside the operating window", None))
    elif all(s == "skipped" for s, *_ in res):
        return [("skipped", "; ".join(m for _, m, _ in res), None)]
    return [x for x in res if x[0] != "skipped"] or res


def _acid_stoichiometry(pt, r, p):
    m = _num(r, p["acid_molarity_field"])
    pd = _num(r, p.get("pulp_density_field", "pulp_density_g_l"))
    if m is None or pd is None:
        return [("skipped", "acid concentration or pulp density missing", None)]
    liquor_l = 1000.0 / pd
    supplied = m * liquor_l
    demand = 0.0
    for el, ratio in p["acid_per_mol"].items():
        key = next((k for k, s in pt.fields.items() if s.get("element") == el), None)
        pct = _num(r, key) if key else None
        if pct:
            demand += pct / 100.0 * 1000.0 / ATOMIC_WEIGHTS[el] * float(ratio)
    res = []
    if supplied < demand:
        res.append(("error", f"acid supplied {supplied:.2f} mol/kg is below the stoichiometric demand {demand:.2f} mol/kg",
                    "raise the acid concentration or lower the pulp density"))
    lo, hi = p.get("ratio_warn_g_per_g", [None, None])
    ratio = supplied * 0.098072
    if lo is not None and not lo <= ratio <= hi:
        res.append(("warning", f"acid-to-solid ratio {ratio:.2f} g/g outside the usual {lo} to {hi}", None))
    return res or [("pass", f"acid {supplied:.2f} mol/kg covers demand {demand:.2f} mol/kg", None)]


def _output_bounds(pt, r, p):
    res = []
    seen = False
    for k, spec in pt.outputs.items():
        v = _num(r, k)
        if v is None:
            continue
        seen = True
        lo, hi = float(spec.get("min", -math.inf)), float(spec.get("max", math.inf))
        if not lo <= v <= hi:
            res.append(("error", f"{k} = {v:g} outside {lo:g} to {hi:g}", None))
    for k, lim in (p.get("warn_below") or {}).items():
        v = _num(r, k)
        if v is not None and v < float(lim):
            res.append(("warning", f"{k} = {v:g} below the expected {lim}", "check the assay or the conditions"))
    if not seen:
        return [("skipped", "no outputs in this run", None)]
    return res or [("pass", "outputs inside their bounds", None)]


def _element_balance(pt, r, p):
    tol = float(p.get("tolerance_pct", 5))
    liquor = _num(r, "liquor_l_per_kg_bm")
    residue = _num(r, "residue_kg_per_kg_bm")
    if liquor is None or residue is None:
        return [("skipped", "liquor and residue assays absent: balance not checked (skipped, not passed)",
                 "add liquor_l_per_kg_bm, residue_kg_per_kg_bm and the element assays")]
    res, worst = [], 0.0
    for el, (feed_k, liq_k, res_k) in p["elements"].items():
        feed, lg, rp = _num(r, feed_k), _num(r, liq_k), _num(r, res_k)
        if None in (feed, lg, rp) or not feed:
            continue
        fin = feed / 100.0
        fout = liquor * lg / 1000.0 + residue * rp / 100.0
        err = abs(fout - fin) / fin * 100.0
        worst = max(worst, err)
        if err > tol:
            res.append(("error", f"{el} balance off by {err:.1f}% (in {fin:.4f}, out {fout:.4f} kg/kg)",
                        "check the liquor volume and assays for this run"))
    return res or [("pass", f"element balances close (worst {worst:.1f}%)", None)]


_RULES = {
    "composition_closure": _composition_closure,
    "operating_window": _operating_window,
    "acid_stoichiometry": _acid_stoichiometry,
    "output_bounds": _output_bounds,
    "element_balance": _element_balance,
}


def rule_summary(pt: ProcessType, findings: list[Finding]) -> list[dict]:
    """Per rule: how many runs passed, warned, failed, skipped."""
    out = []
    for rule in pt.rules:
        fs = [f for f in findings if f.data.get("rule") == rule["id"]]
        runs: dict[str, str] = {}
        rank = {"error": 0, "warning": 1, "skipped": 2, "pass": 3}
        for f in fs:
            cur = runs.get(f.subject or "")
            if cur is None or rank[f.severity] < rank[cur]:
                runs[f.subject or ""] = f.severity
        counts = {s: sum(1 for v in runs.values() if v == s) for s in ("pass", "warning", "error", "skipped")}
        status = "skipped" if not runs else "error" if counts["error"] else "warning" if counts["warning"] else "skipped" if counts["skipped"] and not counts["pass"] else "pass"
        out.append({"id": rule["id"], "title": rule.get("title"), "check": rule["check"], "counts": counts, "status": status})
    return out
