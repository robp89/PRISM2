"""The process library: process types as reviewed configuration (fields, windows, rules, recipe)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import formulas
from .findings import Finding
from .yamlio import LineMap, load_yaml

LIBRARY_DIR = Path(__file__).parent / "library"
EXCHANGE_CATEGORIES = {
    "Material Input", "Energy Input", "Emission to Air", "Emission to Water", "Waste", "Co-product", "Product",
}
XYCLE_UNITS = {"kg", "kWh", "MJ", "m3", "L", "tonne", "t"}
KNOWN_CHECKS = {"composition_closure", "operating_window", "acid_stoichiometry", "output_bounds", "element_balance"}


@dataclass
class ProcessType:
    data: dict
    path: Path
    lines: LineMap = field(default_factory=LineMap)

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def title(self) -> str:
        return self.data.get("title", self.id)

    @property
    def status(self) -> str:
        return self.data.get("status", "draft")

    @property
    def reviewed(self) -> bool:
        return self.status == "reviewed"

    @property
    def fields(self) -> dict[str, dict]:
        return self.data.get("fields", {})

    @property
    def outputs(self) -> dict[str, dict]:
        return self.data.get("outputs", {})

    @property
    def assays(self) -> dict[str, dict]:
        return self.data.get("assays", {}) or {}

    @property
    def rules(self) -> list[dict]:
        return self.data.get("rules", [])

    @property
    def constants(self) -> dict[str, float]:
        return {k: float(v["value"] if isinstance(v, dict) else v) for k, v in (self.data.get("constants") or {}).items()}

    @property
    def derived(self) -> dict[str, str]:
        return {k: str(v) for k, v in (self.data.get("derived") or {}).items()}

    @property
    def exchanges(self) -> list[dict]:
        return self.data.get("exchanges", [])

    @property
    def inputs(self) -> list[str]:
        return list(self.fields)

    def defaults(self) -> dict[str, float]:
        return {k: float(v["default"]) for k, v in self.fields.items() if "default" in v}

    def composition_fields(self) -> list[str]:
        return [k for k, v in self.fields.items() if v.get("group") == "composition"]

    def summary(self) -> dict:
        d = self.data
        return {
            "id": self.id, "title": self.title, "version": d.get("version"), "status": self.status,
            "placeholder": bool(d.get("placeholder")), "route_family": d.get("route_family"), "wp": d.get("wp"),
            "functional_unit": d.get("functional_unit"), "boundary": d.get("boundary"), "owners": d.get("owners"),
            "reviews": d.get("reviews", []), "fields": self.fields, "outputs": self.outputs,
            "rules": [{"id": r["id"], "title": r.get("title"), "check": r["check"]} for r in self.rules],
            "exchanges": self.exchanges, "sources": d.get("sources", []),
        }


def load_process_type(path: str | Path) -> ProcessType:
    data, lines = load_yaml(path)
    return ProcessType(data=data or {}, path=Path(path), lines=lines)


def library_paths(extra_dirs: list[Path] | None = None) -> list[Path]:
    paths = sorted(LIBRARY_DIR.glob("*.yaml"))
    for d in extra_dirs or []:
        paths += sorted(Path(d).glob("*.yaml"))
    return paths


def list_types(extra_dirs: list[Path] | None = None) -> list[ProcessType]:
    return [load_process_type(p) for p in library_paths(extra_dirs)]


def resolve(ref: str, base: Path | None = None) -> ProcessType:
    """A process type by library id (``bml-v1``) or by a path relative to the project."""
    if base is not None and (ref.endswith(".yaml") or "/" in ref):
        return load_process_type((base / ref).resolve())
    p = LIBRARY_DIR / f"{ref}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"process type {ref!r} is not in the library ({', '.join(t.id for t in list_types())})")
    return load_process_type(p)


def check_process_type(pt: ProcessType, rel: str) -> list[Finding]:
    """Schema and consistency checks of a process-type file."""
    out: list[Finding] = []
    d, L = pt.data, pt.lines

    def f(fid, sev, msg, path, fix=None):
        out.append(Finding(f"type.{fid}", sev, msg, rel, L.line(path), fix))

    if d.get("schema") != "prism2/process-type/v1":
        f("schema", "error", "schema must be prism2/process-type/v1", "schema")
    for key in ("id", "title", "status", "functional_unit", "fields", "outputs", "rules", "exchanges"):
        if key not in d:
            f("missing-key", "error", f"missing required key {key!r}", key)
    if d.get("status") not in ("draft", "reviewed", "retired"):
        f("status", "error", "status must be draft, reviewed or retired", "status")
    if d.get("status") == "reviewed" and not d.get("reviews"):
        f("review-record", "error", "status is reviewed but there is no review record", "reviews",
          "add reviews: [{by: <name>, date: YYYY-MM-DD, scope: ...}]")
    if d.get("status") == "draft":
        f("draft", "warning", "process type is a draft: results cannot be rated above tier D", "status",
          "ask the named owners to review and record it under reviews:")
    for k, spec in pt.fields.items():
        if "min" in spec and "max" in spec and float(spec["min"]) > float(spec["max"]):
            f("window", "error", f"field {k}: min is above max", f"fields.{k}")
        if "default" in spec and not (float(spec.get("min", -1e300)) <= float(spec["default"]) <= float(spec.get("max", 1e300))):
            f("default", "error", f"field {k}: default outside its window", f"fields.{k}.default")
    for i, r in enumerate(pt.rules):
        if r.get("check") not in KNOWN_CHECKS:
            f("rule", "error", f"rule {r.get('id')}: unknown check {r.get('check')!r}", f"rules.{i}",
              f"use one of {sorted(KNOWN_CHECKS)}")
    known = set(pt.fields) | set(pt.outputs) | set(pt.constants)
    try:
        formulas.dependency_order(pt.derived, known)
    except formulas.FormulaError as e:
        f("formula", "error", str(e), "derived")
    names = known | set(pt.derived)
    refs = 0
    for i, ex in enumerate(pt.exchanges):
        p = f"exchanges.{i}"
        if ex.get("category") not in EXCHANGE_CATEGORIES:
            f("category", "error", f"exchange {ex.get('key')}: category not accepted by XYCLE", f"{p}.category",
              f"use one of {sorted(EXCHANGE_CATEGORIES)}")
        if ex.get("unit") not in XYCLE_UNITS:
            f("unit", "error", f"exchange {ex.get('key')}: unit {ex.get('unit')!r} not accepted by XYCLE", f"{p}.unit",
              f"use one of {sorted(XYCLE_UNITS)}")
        if ex.get("flow") == "reference":
            refs += 1
        try:
            missing = formulas.names(str(ex.get("formula", ""))) - names
            if missing:
                f("formula", "error", f"exchange {ex.get('key')}: unknown name(s) {sorted(missing)}", f"{p}.formula")
        except formulas.FormulaError as e:
            f("formula", "error", str(e), f"{p}.formula")
    if refs != 1:
        f("reference-flow", "error", f"exactly one exchange must be the reference flow (found {refs})", "exchanges")
    return out
