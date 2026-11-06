import json

import numpy as np
import pytest

from prism2 import build, project, surrogate


def test_surrogates_recover_a_known_function():
    rng = np.random.default_rng(0)
    X = rng.uniform(-1, 1, (80, 3))
    y = 2 + X[:, 0] - 0.5 * X[:, 1] ** 2 + 0.3 * X[:, 0] * X[:, 2]
    tr, ho = surrogate.split(80, 0.2)
    for fam in surrogate.FAMILIES:
        m = surrogate.FITTERS[fam](X[tr], y[tr])
        assert surrogate.metrics(y[ho], surrogate.predict(m, X[ho]))["r2"] > 0.9, fam
        json.dumps(m)  # models are JSON, never pickled
    # the polynomial exported as a formula gives the same numbers
    from prism2 import formulas
    m = surrogate.fit_polynomial(X[tr], y[tr])
    f = surrogate.polynomial_formula(m, ["a", "b", "c"])
    v = formulas.evaluate(f, {"a": X[ho][0, 0], "b": X[ho][0, 1], "c": X[ho][0, 2]})
    assert v == pytest.approx(surrogate.predict(m, X[ho][:1])[0], rel=1e-9)
    assert formulas.to_xycle(f)  # parseable in XYCLE syntax


def test_decision_rule_prefers_polynomial_within_margin():
    r = lambda x: {"holdout": {"r2": x}}
    assert surrogate.choose({"polynomial": r(0.95), "gp": r(0.955)}) == "polynomial"
    assert surrogate.choose({"polynomial": r(0.90), "gp": r(0.99)}) == "gp"


@pytest.fixture
def built(leach):
    prj = project.load(leach)
    out = build.run(prj, demo=True, families=["polynomial", "gp"], n_mc=150)
    return leach, out


def test_build_end_to_end(built):
    root, out = built
    assert out["model"]["n_holdout"] >= 8
    assert set(out["model"]["targets"]) == {"ni_recovery_pct", "co_recovery_pct", "li_recovery_pct", "mn_recovery_pct"}
    for name in ("findings.json", "model.json", "certification.json", "inventory.json", "inventory.csv", "method-note.md", "prism.lock.json"):
        assert (root / "build" / name).exists(), name
    # excluded runs never reach the model
    holdout = set(out["model"]["holdout_ids"])
    assert not holdout & {"mid-031", "high-031"}
    assert out["model"]["n_runs"] == 91
    inv = out["inventory"]
    assert set(inv["grades"]) == {"low", "mid", "high"}
    for g in inv["grades"].values():
        for v in g["exchanges"].values():
            assert v["p5"] <= v["p50"] <= v["p95"]
    # higher-grade feed leaches more nickel
    ni = {g: inv["grades"][g]["exchanges"]["ni_liquor"]["value"] for g in inv["grades"]}
    assert ni["low"] < ni["mid"] < ni["high"]
    assert out["verdict"]["level"] == "Demo"
    assert out["certification"]["tier"] == "D"  # draft process type caps the tier


def test_export_fails_closed_and_demo_is_watermarked(built):
    root, _ = built
    prj = project.load(root)
    with pytest.raises(build.ExportRefused) as e:
        build.export_xycle(prj, demo=False)  # a demo build must not unlock a real export
    assert any("synthetic" in b for b in e.value.blockers)
    r = build.export_xycle(prj, demo=True)
    assert r["watermark"] and all("DEMO" in f for f in r["files"])
    import csv
    from openpyxl import load_workbook
    rows = list(csv.DictReader(open(root / r["files"][0])))
    assert list(rows[0]) == ["Name", "Formula", "Unit", "Description"]
    names = [x["Name"] for x in rows]
    assert names.index("liquor_l") < names.index("acid_kg")  # dependency order
    wb = load_workbook(root / r["files"][1])
    assert len(wb.sheetnames) == 3 and all(len(n) <= 31 for n in wb.sheetnames)
    ws = wb[wb.sheetnames[0]]
    assert [c.value for c in ws[2]][:3] == ["Inventory Item", "Description", "Category"]
    dpp = json.loads((root / r["files"][2]).read_text())
    assert dpp["status"] == "DRAFT_NOT_VALIDATED_AGAINST_ANY_STANDARD"


def test_stale_build_blocks_export(built):
    root, _ = built
    with open(root / "feedstocks.yaml", "a") as fh:
        fh.write("# edited\n")
    prj = project.load(root)
    assert "feedstocks.yaml" in project.stale_inputs(prj)
    with pytest.raises(build.ExportRefused):
        build.export_xycle(prj, demo=True)


def test_screening_path_with_few_runs(smelt):
    prj = project.load(smelt)
    out = build.run(prj, n_mc=50)
    assert out["model"] is None
    assert out["verdict"]["level"] == "Screening only"
    assert out["inventory"]["basis"] == "runs-mean"
    with pytest.raises(build.ExportRefused):
        build.export_xycle(prj)


def test_reviewed_measured_data_can_reach_tier_b(leach):
    """Reviewed process type + measured data + technical sign-off -> Ready (tier B, window not fully covered)."""
    prj = project.load(leach)
    prj.process.data["status"] = "reviewed"
    prj.process.data["reviews"] = [{"by": "reviewer", "date": "2026-11-01"}]
    prj.manifest["data"]["origin"] = "pilot"
    prj.signoffs = [{"role": "technical", "by": "reviewer", "date": "2026-11-02"}]
    out = build.run(prj, families=["gp"], n_mc=50)
    assert out["certification"]["tier"] == "B"
    assert out["certification"]["certified"]
    assert out["verdict"]["level"] == "Ready"
