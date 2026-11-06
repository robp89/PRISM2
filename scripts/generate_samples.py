"""Generate the synthetic example data. Everything here is INVENTED for demonstration; none is evidence.

Recovery follows a shrinking-core-like first-order form with Arrhenius temperature dependence, acid and
peroxide effects (illustrative constants, not fitted to any data). Two runs carry deliberate errors so the
checks have something to find: run high-031 has nickel in the liquor biased +20% (fails R7), run
mid-031 has a temperature outside the window (fails R2).

    python scripts/generate_samples.py
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
from scipy.stats import qmc

ROOT = Path(__file__).resolve().parents[1]
GRADES = {
    "low": {"ni_pct": 12.0, "co_pct": 3.0, "li_pct": 2.5, "mn_pct": 4.0, "al_pct": 3.0, "cu_pct": 2.0, "graphite_pct": 40.0},
    "mid": {"ni_pct": 18.0, "co_pct": 6.0, "li_pct": 3.5, "mn_pct": 6.0, "al_pct": 2.0, "cu_pct": 1.5, "graphite_pct": 35.0},
    "high": {"ni_pct": 24.0, "co_pct": 8.0, "li_pct": 4.5, "mn_pct": 8.0, "al_pct": 1.0, "cu_pct": 1.0, "graphite_pct": 30.0},
}
WINDOW = {"temperature_c": (45, 85), "h2so4_molarity": (1.4, 2.4), "residence_time_min": (45, 200),
          "h2o2_vol_pct": (0.5, 4.0), "pulp_density_g_l": (85, 115)}
ELEMENT = {"ni": (0.99, 1.0, 1.0), "co": (0.985, 1.0, 1.6), "li": (0.975, 0.6, 0.4), "mn": (0.98, 0.9, 1.2)}


def recovery(el: str, x: dict, rng) -> float:
    cap, acid_exp, perox = ELEMENT[el]
    k = (0.02 * math.exp(3500 * (1 / 338.15 - 1 / (x["temperature_c"] + 273.15)))
         * (x["h2so4_molarity"] / 1.5) ** (0.6 * acid_exp) * (1 + 0.12 * perox * x["h2o2_vol_pct"])
         * (100 / x["pulp_density_g_l"]) ** 0.2)
    return float(np.clip(100 * cap * (1 - math.exp(-k * x["residence_time_min"])) + rng.normal(0, 0.4), 0, 100))


def leach_runs(n_per_grade: int = 30, seed: int = 2026) -> list[dict]:
    rng = np.random.default_rng(seed)
    keys = list(WINDOW)
    rows = []
    for gi, (g, comp) in enumerate(GRADES.items()):
        U = qmc.Sobol(len(keys), scramble=True, seed=seed + gi).random(n_per_grade + 2)[:n_per_grade + 1]
        X = qmc.scale(U, [WINDOW[k][0] for k in keys], [WINDOW[k][1] for k in keys])
        for j, xv in enumerate(X):
            x = dict(zip(keys, (round(float(v), 2) for v in xv)))
            row = {"run_id": f"{g}-{j + 1:03d}", "grade": g, **comp, **x}
            leached, residue_el = {}, {}
            for el in ELEMENT:
                rec = recovery(el, x, rng)
                row[f"{el}_recovery_pct"] = round(rec, 2)
                leached[el] = comp[f"{el}_pct"] / 100 * rec / 100
                residue_el[el] = comp[f"{el}_pct"] / 100 - leached[el]
            liquor = 1000 / x["pulp_density_g_l"] * (1 + rng.normal(0, 0.005))
            residue = 1 - sum(leached.values()) - 0.6 * (comp["al_pct"] + comp["cu_pct"]) / 100
            row["liquor_l_per_kg_bm"] = round(liquor, 3)
            row["residue_kg_per_kg_bm"] = round(residue, 4)
            for el in ELEMENT:
                row[f"liquor_{el}_g_l"] = round(leached[el] * 1000 / liquor * (1 + rng.normal(0, 0.008)), 3)
                row[f"residue_{el}_pct"] = round(residue_el[el] / residue * 100 * (1 + rng.normal(0, 0.01)), 3)
            rows.append(row)
    # deliberate errors (documented above)
    bad_bal = next(r for r in rows if r["run_id"] == "high-031")
    bad_bal["liquor_ni_g_l"] = round(bad_bal["liquor_ni_g_l"] * 1.2, 3)
    bad_win = next(r for r in rows if r["run_id"] == "mid-031")
    bad_win["temperature_c"] = 95.0
    return rows


def smelt_runs() -> list[dict]:
    """Eight illustrative 'literature-style' smelting points (invented, labelled as such)."""
    rng = np.random.default_rng(7)
    out = []
    for i, t in enumerate(np.linspace(1400, 1600, 8)):
        out.append({"run_id": f"lit-{i + 1}", "ni_pct": 18, "co_pct": 6, "cu_pct": 2, "li_pct": 3.5, "graphite_pct": 35,
                    "temperature_c": round(float(t)), "flux_kg_per_kg": 0.4, "electricity_kwh_per_kg": round(1.0 + 0.002 * (t - 1400), 2),
                    "ni_recovery_pct": round(float(95 + 0.015 * (t - 1400) + rng.normal(0, 0.4)), 1),
                    "co_recovery_pct": round(float(92 + 0.02 * (t - 1400) + rng.normal(0, 0.5)), 1),
                    "li_to_slag_pct": round(float(97 + rng.normal(0, 0.5)), 1)})
    return out


def write(rows: list[dict], path: Path) -> None:
    keys: list[str] = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    write(leach_runs(), ROOT / "examples/leach-demo/data/runs.csv")
    write(smelt_runs(), ROOT / "examples/smelt-screening/data/runs.csv")
    print("wrote examples/leach-demo/data/runs.csv and examples/smelt-screening/data/runs.csv (synthetic)")
