"""Draft battery passport data block. Explicitly NOT validated against any standard (DPP-1 open)."""
from __future__ import annotations

from datetime import date

from ..project import Project


def build(prj: Project, inventory: dict, cert: dict, hashes: dict) -> dict:
    return {
        "schema": "prism-dpp-draft-0.1",
        "status": "DRAFT_NOT_VALIDATED_AGAINST_ANY_STANDARD",
        "generated": date.today().isoformat(),
        "model": {"id": prj.id, "title": prj.title, "process_type": prj.process.id, "process_type_version": prj.process.data.get("version")},
        "functional_unit": inventory.get("functional_unit"),
        "quality_tier": cert["tier"], "certified": cert["certified"], "demo": cert["demo"],
        "data_origin": prj.origin,
        "foreground_inventory": {g: {k: {"value": v["value"], "p5": v["p5"], "p95": v["p95"]} for k, v in gr["exchanges"].items()}
                                 for g, gr in inventory["grades"].items()},
        "note": "Physical flows only. Carbon footprint and other impacts are calculated in XYCLE with licensed background data.",
        "evidence": {"input_sha256": hashes},
    }
