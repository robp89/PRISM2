"""Inventory generation: physical exchanges per functional unit at a point, across feedstock grades
(low, mid, high envelope), with Monte Carlo ranges and the input that drives each exchange.

No emission factors and no impacts: XYCLE applies background data and characterisation.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from . import formulas, surrogate
from .project import Project

DEFAULT_UNCERTAINTY = {"composition_rel_sd": 0.05, "conditions_rel_sd": 0.02}  # A-14


def _base_env(prj: Project) -> dict[str, float]:
    env = dict(prj.process.defaults())
    env.update(prj.process.constants)
    return env


def point_inputs(prj: Project, grade: str | None) -> dict[str, float]:
    fs = prj.feedstocks or {}
    env = _base_env(prj)
    env.update({k: float(v) for k, v in (fs.get("operating_point") or {}).items()})
    if grade:
        env.update({k: float(v) for k, v in ((fs.get("grades") or {}).get(grade) or {}).items()})
    return env


def predict_outputs(prj: Project, model: dict | None, env: dict[str, float]) -> tuple[dict[str, float], list[str]]:
    """Model outputs at a point, plus applicability-domain warnings."""
    out, warnings = {}, []
    if model:
        X = np.array([[env.get(k, np.nan) for k in model["inputs"]]])
        for k, (lo, hi) in model["input_ranges"].items():
            v = env.get(k)
            if v is not None and not lo - 1e-9 <= v <= hi + 1e-9:
                warnings.append(f"{k} = {v:g} is outside the trained range {lo:g} to {hi:g}: extrapolation")
        for t, res in model["targets"].items():
            fam = res["chosen"]
            v = float(surrogate.predict(res["families"][fam]["model"], X)[0])
            spec = prj.process.outputs.get(t, {})
            out[t] = float(np.clip(v, float(spec.get("min", -np.inf)), float(spec.get("max", np.inf))))
    else:
        for t in prj.process.outputs:
            vals = [float(r[t]) for r in prj.runs if t in r]
            if vals:
                out[t] = float(np.mean(vals))
        if out:
            warnings.append("no fitted model: outputs are the mean of the runs (quick look)")
    missing = [t for t in prj.process.outputs if t not in out]
    ex = (prj.process.data.get("examples") or {}).get("default_point", {})
    for t in missing:
        if t in ex:
            out[t] = float(ex[t])
            warnings.append(f"{t} taken from the process type's illustrative default point")
    return out, warnings


def exchanges_at(prj: Project, env: dict[str, float]) -> dict[str, float]:
    full = formulas.evaluate_all(prj.process.derived, env)
    return {ex["key"]: formulas.evaluate(str(ex["formula"]), full) for ex in prj.process.exchanges}


def generate(prj: Project, model: dict | None, n_mc: int = 2000, seed: int = 5) -> dict:
    grades = list((prj.feedstocks.get("grades") or {}).keys()) or [None]
    unc = {**DEFAULT_UNCERTAINTY, **((prj.feedstocks or {}).get("uncertainty") or {})}
    rng = np.random.default_rng(seed)
    comp_fields = set(prj.process.composition_fields())
    cond_fields = {k for k, s in prj.process.fields.items() if s.get("group") == "conditions"}
    result = {"functional_unit": prj.process.data.get("functional_unit"), "grades": {}, "warnings": [],
              "exchanges": [{k: ex.get(k) for k in ("key", "name", "category", "unit", "assumption", "flow", "note")} for ex in prj.process.exchanges],
              "uncertainty": unc, "n_mc": n_mc, "basis": "model" if model else "runs-mean"}
    for g in grades:
        env = point_inputs(prj, g)
        outs, warns = predict_outputs(prj, model, env)
        env.update(outs)
        values = exchanges_at(prj, env)
        # Monte Carlo
        samples = {k: [] for k in values}
        drivers_in: dict[str, list] = {}
        for _ in range(n_mc):
            e = dict(env)
            for k in comp_fields & set(e):
                e[k] = max(0.0, e[k] * (1 + unc["composition_rel_sd"] * rng.standard_normal()))
            for k in cond_fields & set(e):
                s = prj.process.fields[k]
                e[k] = float(np.clip(e[k] * (1 + unc["conditions_rel_sd"] * rng.standard_normal()), s.get("min", -np.inf), s.get("max", np.inf)))
            o, _ = predict_outputs(prj, model, e) if model else (dict(outs), [])
            for t in o:
                rmse = model["targets"][t]["families"][model["targets"][t]["chosen"]]["holdout"]["rmse"] if model and t in model["targets"] else 0.0
                spec = prj.process.outputs[t]
                o[t] = float(np.clip(o[t] + rmse * rng.standard_normal(), spec.get("min", -np.inf), spec.get("max", np.inf)))
            e.update(o)
            v = exchanges_at(prj, e)
            for k in v:
                samples[k].append(v[k])
            for k in list(comp_fields & set(e)) + list(cond_fields & set(e)) + list(o):
                drivers_in.setdefault(k, []).append(e[k])
        rows = {}
        for k, mid in values.items():
            arr = np.array(samples[k])
            driver, rho = None, 0.0
            if np.ptp(arr) > 0:
                for name, xs in drivers_in.items():
                    xs = np.array(xs)
                    if np.ptp(xs) == 0:
                        continue
                    r = float(stats.spearmanr(xs, arr).statistic)
                    if abs(r) > abs(rho):
                        driver, rho = name, r
            rows[k] = {"value": mid, "p5": float(np.percentile(arr, 5)), "p50": float(np.percentile(arr, 50)),
                       "p95": float(np.percentile(arr, 95)), "driver": driver, "driver_rho": rho}
        result["grades"][g or "point"] = {"inputs": {k: env[k] for k in sorted(env) if k in prj.process.fields or k in prj.process.outputs},
                                          "exchanges": rows, "warnings": warns}
        result["warnings"] += [f"{g}: {w}" for w in warns]
    # envelope across grades
    env_rows = {}
    for ex in prj.process.exchanges:
        k = ex["key"]
        vals = [gr["exchanges"][k]["value"] for gr in result["grades"].values()]
        lows = [gr["exchanges"][k]["p5"] for gr in result["grades"].values()]
        highs = [gr["exchanges"][k]["p95"] for gr in result["grades"].values()]
        env_rows[k] = {"min": min(vals), "max": max(vals), "p5": min(lows), "p95": max(highs)}
    result["envelope"] = env_rows
    return result
