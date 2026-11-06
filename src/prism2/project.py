"""A PRISM model repository: plain files in git, loaded and checked together."""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import library, rules
from .findings import Finding, sort_findings
from .yamlio import LineMap, load_yaml

MANIFEST = "prism.yaml"
ORIGINS = {
    "plant": "measured at an operating plant",
    "pilot": "measured at pilot scale",
    "lab": "measured in the laboratory",
    "simulation": "calculated by a process simulator",
    "literature": "taken from publications",
    "synthetic": "invented for demonstration (never evidence)",
}
MEASURED = {"plant", "pilot", "lab"}
DEFAULT_GATE = {"min_runs": 20, "holdout_fraction": 0.2, "min_holdout_runs": 8, "min_r2": 0.92,
                "max_p90_rel_err_pct": 10.0, "min_normality_p": 0.05}
INTENDED_USES = {"screening", "internal_decision", "customer_report", "regulatory_input"}


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass
class Project:
    root: Path
    manifest: dict
    lines: LineMap
    process: library.ProcessType
    scope: dict = field(default_factory=dict)
    scope_lines: LineMap = field(default_factory=LineMap)
    feedstocks: dict = field(default_factory=dict)
    feedstock_lines: LineMap = field(default_factory=LineMap)
    signoffs: list = field(default_factory=list)
    signoff_lines: LineMap = field(default_factory=LineMap)
    runs: list[dict] = field(default_factory=list)
    run_lines: list[int] = field(default_factory=list)
    load_findings: list[Finding] = field(default_factory=list)

    # ---- convenience -------------------------------------------------------------
    @property
    def id(self) -> str:
        return self.manifest.get("id", self.root.name)

    @property
    def title(self) -> str:
        return self.manifest.get("title", self.id)

    @property
    def data_spec(self) -> dict:
        return self.manifest.get("data") or {}

    @property
    def origin(self) -> str:
        return self.data_spec.get("origin", "unknown")

    @property
    def runs_path(self) -> Path | None:
        p = self.data_spec.get("runs")
        return self.root / p if p else None

    @property
    def gate(self) -> dict:
        return {**DEFAULT_GATE, **(self.manifest.get("gate") or {})}

    @property
    def model_spec(self) -> dict:
        return self.manifest.get("model") or {}

    @property
    def targets(self) -> list[str]:
        return self.model_spec.get("targets") or list(self.process.outputs)

    @property
    def build_dir(self) -> Path:
        return self.root / "build"

    def rel(self, p: Path | str) -> str:
        try:
            return str(Path(p).resolve().relative_to(self.root.resolve()))
        except ValueError:
            return str(p)

    def input_files(self) -> list[Path]:
        files = [self.root / MANIFEST, self.root / "scope.yaml", self.root / "feedstocks.yaml",
                 self.root / "signoffs.yaml", self.process.path]
        if self.runs_path:
            files.append(self.runs_path)
        return [f for f in files if f.exists()]

    def input_hashes(self) -> dict[str, str]:
        out = {}
        for f in self.input_files():
            key = self.rel(f) if f.resolve().is_relative_to(self.root.resolve()) else f"library/{f.name}"
            out[key] = sha256(f)
        return out

    @property
    def excluded(self) -> dict[str, str]:
        """Runs left out on purpose, recorded in prism.yaml with a reason (data.exclude)."""
        return {str(e.get("run")): str(e.get("reason", "")) for e in (self.data_spec.get("exclude") or []) if isinstance(e, dict)}

    def run_id(self, i: int) -> str:
        return str(self.runs[i].get("run_id") or self.runs[i].get("run") or f"row{i + 1}")


def _read_runs(prj: Project) -> None:
    p = prj.runs_path
    if p is None:
        return
    rel = prj.rel(p)
    if not p.exists():
        prj.load_findings.append(Finding("data.missing-file", "error", f"run file {rel} does not exist", MANIFEST,
                                         prj.lines.line("data.runs"), "add the file or fix the path in prism.yaml"))
        return
    known = set(prj.process.fields) | set(prj.process.outputs) | set(prj.process.assays) | {"run_id", "run", "note", "grade"}
    with p.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        headers = [h.strip() for h in reader.fieldnames or []]
        unknown = [h for h in headers if h not in known]
        if unknown:
            prj.load_findings.append(Finding("data.unknown-columns", "warning", f"columns ignored: {', '.join(unknown)}",
                                             rel, 1, "rename them to the process type's field keys if they matter"))
        seen = set()
        for i, row in enumerate(reader):
            line = i + 2
            run: dict[str, Any] = {}
            for k, v in row.items():
                k = (k or "").strip()
                v = (v or "").strip()
                if k not in known or v == "":
                    continue
                if k in ("run_id", "run", "note", "grade"):
                    run[k] = v
                    continue
                try:
                    run[k] = float(v)
                except ValueError:
                    prj.load_findings.append(Finding("data.not-a-number", "error", f"{k} = {v!r} is not a number", rel, line,
                                                     subject=run.get("run_id")))
            rid = run.get("run_id") or run.get("run") or f"row{i + 1}"
            if rid in seen:
                prj.load_findings.append(Finding("data.duplicate-run", "error", f"duplicate run id {rid}", rel, line))
            seen.add(rid)
            prj.runs.append(run)
            prj.run_lines.append(line)


def load(root: str | Path) -> Project:
    root = Path(root).resolve()
    mpath = root / MANIFEST
    if not mpath.exists():
        raise FileNotFoundError(f"{mpath} not found: not a PRISM model repository (run `prism init`)")
    manifest, lines = load_yaml(mpath)
    manifest = manifest or {}
    process = library.resolve(str(manifest.get("process_type", "")), base=root)
    prj = Project(root=root, manifest=manifest, lines=lines, process=process)
    for name, attr in (("scope.yaml", "scope"), ("feedstocks.yaml", "feedstocks")):
        p = root / name
        if p.exists():
            d, L = load_yaml(p)
            setattr(prj, attr, d or {})
            setattr(prj, f"{'feedstock' if attr == 'feedstocks' else attr}_lines", L)
    p = root / "signoffs.yaml"
    if p.exists():
        d, L = load_yaml(p)
        prj.signoffs = (d or {}).get("signoffs", []) or []
        prj.signoff_lines = L
    _read_runs(prj)
    return prj


# ---- checks ------------------------------------------------------------------------

def check_manifest(prj: Project) -> list[Finding]:
    out: list[Finding] = []
    m, L = prj.manifest, prj.lines
    if m.get("schema") != "prism2/project/v1":
        out.append(Finding("project.schema", "error", "schema must be prism2/project/v1", MANIFEST, L.line("schema")))
    if prj.origin not in ORIGINS:
        out.append(Finding("project.origin", "error", f"data.origin must be one of {', '.join(ORIGINS)}", MANIFEST,
                           L.line("data.origin"), "say where the numbers came from: it decides how far they can be trusted"))
    if prj.origin == "simulation" and not (prj.data_spec.get("tool") or {}).get("version"):
        out.append(Finding("project.tool-version", "warning", "simulation data without a tool name and version",
                           MANIFEST, L.line("data.tool", "data"), "add data.tool: {name: HSC Sim, version: ...}"))
    for t in prj.targets:
        if t not in prj.process.outputs:
            out.append(Finding("project.target", "error", f"model target {t} is not an output of {prj.process.id}",
                               MANIFEST, L.line("model.targets")))
    return out


def check_scope(prj: Project) -> list[Finding]:
    s, L, f = prj.scope, prj.scope_lines, "scope.yaml"
    if not s:
        return [Finding("scope.missing", "error", "no scope card (scope.yaml)", f, 1, "run `prism init` or copy the template")]
    out = []
    for k in ("goal", "functional_unit", "boundary", "intended_use", "target_tier"):
        if not s.get(k):
            out.append(Finding("scope.missing-field", "error", f"scope card is missing {k}", f, L.line(k, "goal")))
    if s.get("intended_use") and s["intended_use"] not in INTENDED_USES:
        out.append(Finding("scope.intended-use", "error", f"intended_use must be one of {sorted(INTENDED_USES)}", f, L.line("intended_use")))
    if s.get("target_tier") and s["target_tier"] not in ("A", "B", "C", "D"):
        out.append(Finding("scope.tier", "error", "target_tier must be A, B, C or D", f, L.line("target_tier")))
    fu = prj.process.data.get("functional_unit", {})
    want = f"{fu.get('amount')} {fu.get('unit')} {fu.get('of')}"
    if s.get("functional_unit") and str(fu.get("of", "")).split(" ")[0] not in str(s["functional_unit"]):
        out.append(Finding("scope.functional-unit", "warning",
                           f"functional unit '{s['functional_unit']}' does not match the process type's '{want}'",
                           f, L.line("functional_unit"), "align the scope card or convert the inventory in XYCLE"))
    if "cradle" in str(s.get("boundary", "")).lower() and "gate-to-gate" in str(prj.process.data.get("boundary", "")):
        out.append(Finding("scope.boundary", "error",
                           "scope says cradle-to-gate but the process type is gate-to-gate: the inventory is a foreground unit process only",
                           f, L.line("boundary"), "set boundary to gate-to-gate and link upstream in XYCLE"))
    if not s.get("agreed_by"):
        out.append(Finding("scope.not-agreed", "warning", "functional unit and boundary not yet agreed by the LCA practitioner",
                           f, L.line("agreed_by", "goal"), "add agreed_by: {name: ..., date: ...}"))
    return out


def check_feedstocks(prj: Project) -> list[Finding]:
    g = (prj.feedstocks or {}).get("grades") or {}
    L, f = prj.feedstock_lines, "feedstocks.yaml"
    out = []
    if not g:
        return [Finding("feedstock.missing", "warning", "no feedstock grades: only a single-point inventory is possible", f, 1,
                        "add grades: {low: ..., mid: ..., high: ...}")]
    comp = prj.process.composition_fields()
    for name, vals in g.items():
        for k in comp:
            if prj.process.fields[k].get("required") and k not in (vals or {}):
                out.append(Finding("feedstock.missing-element", "error", f"grade {name} lacks {k}", f, L.line(f"grades.{name}")))
        total = sum(float(v) for k, v in (vals or {}).items() if k in comp)
        if total > 100.5:
            out.append(Finding("feedstock.closure", "error", f"grade {name} sums to {total:.1f} wt%", f, L.line(f"grades.{name}")))
    return out


def check_signoffs(prj: Project) -> list[Finding]:
    out = []
    for i, s in enumerate(prj.signoffs):
        for k in ("role", "by", "date"):
            if not s.get(k):
                out.append(Finding("signoff.incomplete", "error", f"sign-off {i + 1} lacks {k}", "signoffs.yaml",
                                   prj.signoff_lines.line(f"signoffs.{i}")))
        if s.get("role") not in ("technical", "independent", "lca"):
            out.append(Finding("signoff.role", "error", "role must be technical, independent or lca", "signoffs.yaml",
                               prj.signoff_lines.line(f"signoffs.{i}.role")))
    return out


def check_runs(prj: Project) -> list[Finding]:
    rel = prj.rel(prj.runs_path) if prj.runs_path else None
    out = []
    for i, run in enumerate(prj.runs):
        out += rules.check_run(prj.process, run, file=rel, line=prj.run_lines[i], run_id=prj.run_id(i))
    return out


def validate(prj: Project, *, include_pass: bool = False) -> list[Finding]:
    ptype_rel = prj.rel(prj.process.path) if prj.process.path.resolve().is_relative_to(prj.root) else f"library/{prj.process.path.name}"
    out = (prj.load_findings + check_manifest(prj) + check_scope(prj) + check_feedstocks(prj) + check_signoffs(prj)
           + library.check_process_type(prj.process, ptype_rel) + check_runs(prj))
    if prj.origin == "synthetic":
        out.append(Finding("data.synthetic", "warning", "the run data is synthetic: results are a demonstration and cannot be exported outside demo mode",
                           MANIFEST, prj.lines.line("data.origin")))
    exc = prj.excluded
    ids = {prj.run_id(i) for i in range(len(prj.runs))}
    for i, e in enumerate(prj.data_spec.get("exclude") or []):
        if not isinstance(e, dict) or not e.get("reason"):
            out.append(Finding("data.exclude-reason", "error", "every excluded run needs a reason", MANIFEST,
                               prj.lines.line(f"data.exclude.{i}"), "exclude: [{run: <id>, reason: ...}]"))
        elif str(e.get("run")) not in ids:
            out.append(Finding("data.exclude-unknown", "warning", f"excluded run {e.get('run')} is not in the data",
                               MANIFEST, prj.lines.line(f"data.exclude.{i}")))
    for f in out:
        if f.subject in exc and f.severity in ("error", "warning"):
            f.message = f"(excluded: {exc[f.subject]}) {f.message}"
            f.severity = "info"
    if exc:
        out.append(Finding("data.excluded", "info", f"{len(exc)} run(s) excluded from the model: {', '.join(exc)}",
                           MANIFEST, prj.lines.line("data.exclude")))
    if not include_pass:
        out = [f for f in out if f.severity != "pass"]
    return sort_findings(out)


# ---- the build lock: detect outdated results ------------------------------------------

def lock_path(prj: Project) -> Path:
    return prj.build_dir / "prism.lock.json"


def read_lock(prj: Project) -> dict | None:
    p = lock_path(prj)
    return json.loads(p.read_text()) if p.exists() else None


def stale_inputs(prj: Project) -> list[str]:
    lock = read_lock(prj)
    if not lock:
        return ["(never built)"]
    now = prj.input_hashes()
    was = lock.get("inputs", {})
    return sorted(k for k in set(now) | set(was) if now.get(k) != was.get(k))
