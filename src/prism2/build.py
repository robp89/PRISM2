"""The pipeline: validate -> cover -> fit and benchmark -> certify -> inventory -> write outputs.

Outputs go to ``build/`` with a lock file of input hashes, so ``prism status`` can tell when a result
is outdated (the ChemE-as-Code idea of flagging stale results, applied to inventories).
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import __version__, certify, doe, inventory, rules, surrogate
from .exporters import dpp, method_note, xycle
from .findings import Finding
from .project import Project, read_lock, stale_inputs, validate


class ExportRefused(RuntimeError):
    def __init__(self, blockers: list[str]):
        super().__init__("export refused: " + "; ".join(blockers))
        self.blockers = blockers


def model_inputs(prj: Project) -> list[str]:
    keys = [k for k in prj.process.fields if any(k in r for r in prj.runs)]
    return [k for k in keys if np.ptp([float(r.get(k, prj.process.defaults().get(k, np.nan))) for r in prj.runs]) > 0]


def clean_runs(prj: Project, findings: list[Finding]) -> list[int]:
    bad = {f.subject for f in findings if f.severity == "error" and f.subject} | set(prj.excluded)
    return [i for i in range(len(prj.runs)) if prj.run_id(i) not in bad]


def fit(prj: Project, findings: list[Finding], families: list[str] | None = None, seed: int = 42) -> dict | None:
    idx = clean_runs(prj, findings)
    if len(idx) < prj.gate["min_runs"]:
        return None
    fams = families or prj.model_spec.get("families") or list(surrogate.FAMILIES)
    degree = int(prj.model_spec.get("degree", 2))
    inputs = model_inputs(prj)
    d = prj.process.defaults()
    X_all = np.array([[float(prj.runs[i].get(k, d.get(k, np.nan))) for k in inputs] for i in idx])
    tr, ho = surrogate.split(len(idx), prj.gate["holdout_fraction"], seed)
    out = {"inputs": inputs, "input_ranges": {k: [float(X_all[tr, j].min()), float(X_all[tr, j].max())] for j, k in enumerate(inputs)},
           "n_runs": len(idx), "n_train": int(len(tr)), "n_holdout": int(len(ho)), "seed": seed,
           "holdout_ids": [prj.run_id(idx[i]) for i in ho], "families": fams,
           "decision_rule": "highest held-out R² per output; polynomial preferred within 0.01 because it exports as a formula",
           "targets": {}}
    lo, hi = X_all[tr].min(axis=0), X_all[tr].max(axis=0)
    for t in prj.targets:
        rows = [j for j, i in enumerate(idx) if t in prj.runs[i]]
        if len(rows) < prj.gate["min_runs"]:
            continue
        y_all = np.array([float(prj.runs[idx[j]][t]) if t in prj.runs[idx[j]] else np.nan for j in range(len(idx))])
        trt = np.array([j for j in tr if not np.isnan(y_all[j])])
        hot = np.array([j for j in ho if not np.isnan(y_all[j])])
        res = {"families": {}}
        for fam in fams:
            kw = {"degree": degree} if fam == "polynomial" else {}
            m = surrogate.FITTERS[fam](X_all[trt], y_all[trt], **kw)
            res["families"][fam] = {"model": m, "holdout": surrogate.metrics(y_all[hot], surrogate.predict(m, X_all[hot])),
                                    "train": surrogate.metrics(y_all[trt], surrogate.predict(m, X_all[trt])),
                                    "cv_r2": surrogate.kfold_r2(fam, X_all[trt], y_all[trt], **kw) if fam != "ann" else None}
        res["chosen"] = surrogate.choose(res["families"])
        res["sobol"] = dict(zip(("first_order", "total"), surrogate.sobol_indices(res["families"][res["chosen"]]["model"], lo, hi).values()))
        res["holdout_points"] = {"y": y_all[hot].tolist(), "yhat": surrogate.predict(res["families"][res["chosen"]]["model"], X_all[hot]).tolist()}
        out["targets"][t] = res
    return out


def _json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=1, default=float), encoding="utf-8")


def run(prj: Project, *, demo: bool = False, families: list[str] | None = None, n_mc: int = 1000) -> dict:
    findings = validate(prj, include_pass=True)
    rule_rows = rules.rule_summary(prj.process, findings)
    cov = doe.coverage(prj)
    model = fit(prj, findings, families)
    shown = [f for f in findings if f.severity != "pass"]
    cert = certify.assess(prj, shown, model, cov, demo=demo)
    inv = inventory.generate(prj, model, n_mc=n_mc)
    verdict = certify.verdict(prj, shown, model, cov, cert, rule_rows)
    hashes = prj.input_hashes()

    b = prj.build_dir
    b.mkdir(exist_ok=True)
    _json(b / "findings.json", [f.to_dict() for f in shown])
    _json(b / "rules.json", rule_rows)
    _json(b / "coverage.json", cov)
    if model:
        _json(b / "model.json", model)
    elif (b / "model.json").exists():
        (b / "model.json").unlink()
    _json(b / "certification.json", cert)
    _json(b / "verdict.json", verdict)
    _json(b / "inventory.json", inv)
    with (b / "inventory.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["grade", "key", "name", "category", "unit", "value", "p5", "p50", "p95", "driver"])
        for g, gr in inv["grades"].items():
            for ex in prj.process.exchanges:
                v = gr["exchanges"][ex["key"]]
                w.writerow([g, ex["key"], ex["name"], ex["category"], ex["unit"], f"{v['value']:.6g}", f"{v['p5']:.6g}", f"{v['p50']:.6g}", f"{v['p95']:.6g}", v["driver"] or ""])
    (b / "method-note.md").write_text(method_note.render(prj, model, inv, cert, cov, hashes), encoding="utf-8")
    _json(b / "prism.lock.json", {"prism_version": __version__, "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                  "demo": demo, "inputs": hashes})
    return {"findings": shown, "rules": rule_rows, "coverage": cov, "model": model, "certification": cert,
            "inventory": inv, "verdict": verdict}


def export_xycle(prj: Project, *, demo: bool = False, grade: str | None = None) -> dict:
    """Write the XYCLE files. Fails closed: refuses if the build is stale or certification has blockers."""
    stale = stale_inputs(prj)
    if stale:
        raise ExportRefused([f"build is outdated or missing ({', '.join(stale)}): run `prism build`"])
    b = prj.build_dir
    # always re-assess with the mode asked for now: a demo build must never let a real export through
    shown = [Finding(**{k: v for k, v in f.items() if k != "where"}) for f in json.loads((b / "findings.json").read_text())]
    model_saved = json.loads((b / "model.json").read_text()) if (b / "model.json").exists() else None
    cert = certify.assess(prj, shown, model_saved, json.loads((b / "coverage.json").read_text()), demo=demo)
    if cert["blockers"]:
        raise ExportRefused(cert["blockers"])
    inv = json.loads((b / "inventory.json").read_text())
    model = json.loads((b / "model.json").read_text()) if (b / "model.json").exists() else None
    out = b / "xycle"
    out.mkdir(exist_ok=True)
    g = grade or ("mid" if "mid" in inv["grades"] else next(iter(inv["grades"])))
    point = inv["grades"][g]["inputs"]
    rows, notes = xycle.parameter_rows(prj, model, point)
    suffix = "-DEMO" if cert.get("watermark") else ""
    pfile, mfile = out / f"parameter-import{suffix}.csv", out / f"model-import{suffix}.xlsx"
    xycle.write_parameter_csv(rows, pfile)
    sheets = xycle.write_model_xlsx(prj, inv, mfile, watermark=bool(cert.get("watermark")))
    dfile = out / f"dpp-draft{suffix}.json"
    _json(dfile, dpp.build(prj, inv, cert, prj.input_hashes()))
    return {"files": [prj.rel(pfile), prj.rel(mfile), prj.rel(dfile)], "sheets": sheets, "notes": notes,
            "watermark": bool(cert.get("watermark")), "grade": g}


def snapshot(prj: Project) -> dict:
    """Everything the viewer shows, without rebuilding: live checks plus the last build if present."""
    findings = validate(prj, include_pass=True)
    rule_rows = rules.rule_summary(prj.process, findings)
    shown = [f for f in findings if f.severity != "pass"]
    cov = doe.coverage(prj)
    b = prj.build_dir

    def rd(name):
        p = b / name
        return json.loads(p.read_text()) if p.exists() else None

    model, inv = rd("model.json"), rd("inventory.json")
    # the verdict always shows the real (non-demo) certification, even after a demo build
    cert = certify.assess(prj, shown, model, cov, demo=False)
    verdict = certify.verdict(prj, shown, model, cov, cert, rule_rows)
    stale = stale_inputs(prj)
    lock = read_lock(prj)
    for m in (model or {}).get("targets", {}).values():  # weights are not needed by the viewer
        for f in m["families"].values():
            f.pop("model", None)
    return {"id": prj.id, "title": prj.title, "manifest": prj.manifest, "scope": prj.scope, "feedstocks": prj.feedstocks,
            "signoffs": prj.signoffs, "process": prj.process.summary(), "origin": prj.origin, "n_runs": len(prj.runs),
            "runs_preview": prj.runs[:12], "findings": [f.to_dict() for f in shown], "rules": rule_rows, "coverage": cov,
            "model": model, "certification": cert, "inventory": inv, "verdict": verdict, "stale": stale,
            "built_at": (lock or {}).get("built_at"), "method_note": (b / "method-note.md").read_text() if (b / "method-note.md").exists() else None,
            "gate": prj.gate}
