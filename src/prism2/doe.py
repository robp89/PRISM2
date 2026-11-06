"""Design of runs (DOE-1): a space-filling run sheet over the operating window and the feedstock
grades, and a coverage check of the runs that came back."""
from __future__ import annotations

import numpy as np
from scipy.stats import qmc

from .project import Project


def design_fields(prj: Project) -> list[str]:
    return [k for k, s in prj.process.fields.items() if s.get("group") == "conditions"]


def generate(prj: Project, n_per_grade: int = 16, method: str = "sobol", seed: int = 1) -> list[dict]:
    fields = design_fields(prj)
    lo = np.array([float(prj.process.fields[k]["min"]) for k in fields])
    hi = np.array([float(prj.process.fields[k]["max"]) for k in fields])
    grades = (prj.feedstocks.get("grades") or {"mid": {}})
    rows = []
    for gi, (gname, comp) in enumerate(grades.items()):
        if method == "lhs":
            U = qmc.LatinHypercube(d=len(fields), seed=seed + gi).random(n_per_grade)
        else:
            U = qmc.Sobol(d=len(fields), scramble=True, seed=seed + gi).random(n_per_grade)
        X = qmc.scale(U, lo, hi)
        for j, x in enumerate(X):
            row = {"run_id": f"{gname}-{j + 1:03d}", "grade": gname}
            row.update({k: round(float(v), 4) for k, v in (comp or {}).items()})
            row.update({k: round(float(v), 3) for k, v in zip(fields, x)})
            rows.append(row)
    return rows


def coverage(prj: Project, bins: int = 4) -> dict:
    """Share of window bins that hold at least one run, per field, and runs per grade."""
    fields = design_fields(prj)
    per_field = {}
    for k in fields:
        s = prj.process.fields[k]
        lo, hi = float(s["min"]), float(s["max"])
        vals = [float(r[k]) for r in prj.runs if k in r]
        if not vals:
            per_field[k] = {"filled": 0, "bins": bins, "share": 0.0, "observed": None}
            continue
        edges = np.linspace(lo, hi, bins + 1)
        filled = len({min(int(np.searchsorted(edges, v, side="right")) - 1, bins - 1) for v in vals if lo <= v <= hi})
        per_field[k] = {"filled": filled, "bins": bins, "share": filled / bins, "observed": [min(vals), max(vals)]}
    grades = list((prj.feedstocks.get("grades") or {}).keys())
    per_grade = {g: sum(1 for r in prj.runs if r.get("grade") == g) for g in grades}
    share = float(np.mean([v["share"] for v in per_field.values()])) if per_field else 0.0
    gaps = [k for k, v in per_field.items() if v["share"] < 0.75]
    missing_grades = [g for g, n in per_grade.items() if n == 0]
    return {"fields": per_field, "grades": per_grade, "share": share, "gaps": gaps, "missing_grades": missing_grades,
            "complete": not gaps and not missing_grades}
