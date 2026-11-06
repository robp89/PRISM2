"""XYCLE import files, built to the written importer rules (Spec 2 section 5).

* Parameter Import (.csv): Name, Formula, Unit, Description; snake_case names; formulas with
  + - * / parentheses and {{name}}; parameters in dependency order. Only polynomial models can be
  written as formulas.
* Model Import (.xlsx): one sheet per unit process; a Process block then an Outbound block, each with
  the ten exact column headers.

Not yet imported into a live XYCLE workspace: try a demo export in a test workspace first.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from openpyxl import Workbook

from .. import formulas, surrogate
from ..project import Project

HEADERS = ["Inventory Item", "Description", "Category", "Type", "Value", "Units", "Reference Unit (FU)",
           "Target Unit Process", "Info Source", "Scope"]
SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")


def parameter_rows(prj: Project, model: dict | None, point: dict[str, float]) -> tuple[list[dict], list[str]]:
    """Rows of the Parameter Import, and notes on what could not be expressed as a formula."""
    pt = prj.process
    rows, notes = [], []
    for k, spec in pt.fields.items():
        if k in point:
            rows.append({"Name": k, "Formula": repr(float(point[k])), "Unit": spec.get("unit", ""), "Description": f"input: {spec.get('label', k)}"})
    for k, v in pt.constants.items():
        rows.append({"Name": k, "Formula": repr(v), "Unit": "", "Description": f"constant ({(pt.data['constants'][k] or {}).get('source', '')})"})
    for t, spec in pt.outputs.items():
        res = (model or {}).get("targets", {}).get(t)
        if res and "polynomial" in res["families"] and res["chosen"] == "polynomial":
            f = surrogate.polynomial_formula(res["families"]["polynomial"]["model"], model["inputs"])
            rows.append({"Name": t, "Formula": formulas.to_xycle(f), "Unit": spec.get("unit", ""), "Description": f"fitted polynomial: {spec.get('label', t)}"})
        else:
            rows.append({"Name": t, "Formula": repr(float(point.get(t, 0.0))), "Unit": spec.get("unit", ""),
                         "Description": f"value at the operating point: {spec.get('label', t)}"})
            if res:
                notes.append(f"{t}: chosen model is {res['chosen']}, which cannot be a formula; exported as a point value")
    for k in formulas.dependency_order(pt.derived, set(pt.fields) | set(pt.constants) | set(pt.outputs)):
        rows.append({"Name": k, "Formula": formulas.to_xycle(pt.derived[k]), "Unit": "", "Description": "derived (recipe)"})
    for r in rows:
        if not SNAKE.match(r["Name"]):
            raise ValueError(f"parameter name {r['Name']!r} is not snake_case")
        if not re.fullmatch(r"[0-9eE.{}a-z_+\-*/() ]+", r["Formula"]):
            raise ValueError(f"formula of {r['Name']} has characters XYCLE does not accept: {r['Formula']}")
    return rows, notes


def write_parameter_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["Name", "Formula", "Unit", "Description"])
        w.writeheader()
        w.writerows(rows)


def _sheet_name(s: str) -> str:
    return re.sub(r"[\[\]:*?/\\]", "", s)[:31]


def write_model_xlsx(prj: Project, inventory: dict, path: Path, watermark: bool) -> list[str]:
    """One sheet per feedstock grade (each is a unit process variant)."""
    wb = Workbook()
    wb.remove(wb.active)
    fu = prj.process.data.get("functional_unit", {})
    fu_text = f"{fu.get('amount', 1)} {fu.get('unit', 'kg')} {fu.get('of', '')}".strip()
    sheets = []
    for grade, gr in inventory["grades"].items():
        name = _sheet_name(f"{prj.process.id} {grade}")
        ws = wb.create_sheet(name)
        sheets.append(name)
        ref = next(ex for ex in prj.process.exchanges if ex.get("flow") == "reference")
        info = "PRISM2 " + ("DEMO - NOT FOR USE" if watermark else "certified")
        ws.append(["Process"])
        ws.append(HEADERS)
        for ex in prj.process.exchanges:
            if ex is ref or ex["category"] in ("Co-product", "Product"):
                continue
            v = gr["exchanges"][ex["key"]]
            ws.append([ex["name"], f"p5 {v['p5']:.4g}, p95 {v['p95']:.4g}", ex["category"], "Input" if "Input" in ex["category"] else "Output",
                       round(v["value"], 6), ex["unit"], fu_text, None, info, "Foreground"])
        ws.append([])
        ws.append(["Outbound"])
        ws.append(HEADERS)
        ws.append([ref["name"], "reference flow", "Product", "Output", 1, ref["unit"], fu_text, None, info, "Foreground"])
        for ex in prj.process.exchanges:
            if ex["category"] == "Co-product":
                v = gr["exchanges"][ex["key"]]
                ws.append([ex["name"], f"p5 {v['p5']:.4g}, p95 {v['p95']:.4g}", "Co-product", "Output", round(v["value"], 6), ex["unit"], fu_text, None, info, "Foreground"])
    wb.save(path)
    return sheets
