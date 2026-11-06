"""Findings: every check result carries a stable id, a severity and a file:line location,
so that people and agents can act on it (the ChemE-as-Code convention)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Severity = Literal["error", "warning", "info", "skipped", "pass"]

SEVERITY_ORDER = {"error": 0, "warning": 1, "skipped": 2, "info": 3, "pass": 4}


@dataclass
class Finding:
    id: str  # stable id, e.g. "R3.acid-stoichiometry" or "schema.missing-field"
    severity: Severity
    message: str
    file: str | None = None
    line: int | None = None
    fix: str | None = None  # a plain-language hint
    subject: str | None = None  # e.g. a run id or a field key
    data: dict = field(default_factory=dict)

    def where(self) -> str:
        if self.file and self.line:
            return f"{self.file}:{self.line}"
        return self.file or "-"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["where"] = self.where()
        return d

    def format(self) -> str:
        sub = f" [{self.subject}]" if self.subject else ""
        s = f"{self.where()}: {self.severity}: {self.id}{sub}: {self.message}"
        if self.fix:
            s += f"\n    fix: {self.fix}"
        return s


def sort_findings(items: list[Finding]) -> list[Finding]:
    return sorted(items, key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.file or "", f.line or 0, f.id))


def summarise(items: list[Finding]) -> dict[str, int]:
    out = {k: 0 for k in SEVERITY_ORDER}
    for f in items:
        out[f.severity] = out.get(f.severity, 0) + 1
    return out
