import math

import pytest

from prism2 import chem, formulas, library, project, rules


def test_formula_parser_and_hydrates():
    assert chem.molar_mass("H2SO4") == pytest.approx(98.072, abs=1e-3)
    assert chem.composition("NiSO4.6H2O") == {"Ni": 1, "S": 1, "O": 10, "H": 12}
    assert chem.composition("Ni(OH)2(s)")["H"] == 2
    with pytest.raises(ValueError):
        chem.composition("Xx2")


def test_formulas_safe_and_xycle_syntax():
    assert formulas.evaluate("a * (b - 1) / 2 + c ** 2", {"a": 4, "b": 3, "c": 3}) == 13
    assert formulas.to_xycle("a*(b-c)+x**2") == "{{a}}*({{b}} - {{c}}) + {{x}}*{{x}}"
    for bad in ("__import__('os')", "a.b", "f(x)", "x ** 0.5", "[1]"):
        with pytest.raises(formulas.FormulaError):
            formulas.parse(bad)
    with pytest.raises(formulas.FormulaError):
        formulas.dependency_order({"a": "b + 1", "b": "a + 1"}, set())


def test_library_types_are_valid():
    for pt in library.list_types():
        errors = [f for f in library.check_process_type(pt, pt.path.name) if f.severity == "error"]
        assert not errors, [f.format() for f in errors]
        assert pt.status == "draft"  # nothing is reviewed until the owners say so


def test_leach_recipe_reproduces_the_worked_example():
    """User Journey worked example: 1.47 kg acid, 0.067 kg H2O2, 0.01 m3 water, ~2.5 MJ, residue ~0.68 kg."""
    pt = library.resolve("bml-v1")
    env = {**pt.defaults(), **pt.constants, **pt.data["examples"]["default_point"]}
    full = formulas.evaluate_all(pt.derived, env)
    assert full["acid_kg"] == pytest.approx(1.47, abs=0.005)
    assert full["h2o2_kg"] == pytest.approx(0.067, abs=0.001)
    assert full["water_m3"] == pytest.approx(0.01)
    assert full["heat_mj"] == pytest.approx(2.5, abs=0.1)
    assert full["ni_leached_kg"] == pytest.approx(0.173, abs=0.001)
    assert full["residue_kg"] == pytest.approx(0.68, abs=0.005)
    assert full["o2_kg"] == pytest.approx(0.03, abs=0.002)


def _rule(pt, run, rid):
    return [f for f in rules.check_run(pt, run) if f.data["rule"] == rid]


def test_rules_fail_skip_and_pass():
    pt = library.resolve("bml-v1")
    good = dict(pt.data["examples"]["default_point"])
    assert {f.severity for f in rules.check_run(pt, good)} <= {"pass", "skipped", "warning"}
    # skipped, never pass, without assays
    r7 = _rule(pt, good, "R7")
    assert r7[0].severity == "skipped"
    # acid below stoichiometric demand fails
    weak = {**good, "h2so4_molarity": 0.5, "pulp_density_g_l": 200}
    assert any(f.severity == "error" for f in _rule(pt, weak, "R3"))
    # outside the window fails
    hot = {**good, "temperature_c": 95}
    assert _rule(pt, hot, "R2")[0].severity == "error"
    # composition over 100.5 fails
    assert _rule(pt, {**good, "ni_pct": 95}, "R1")[0].severity == "error"


def test_validate_points_at_file_and_line(leach):
    prj = project.load(leach)
    # remove the recorded exclusions: the two planted errors must be found at their rows
    prj.manifest["data"].pop("exclude")
    fs = project.validate(prj)
    errs = {(f.id, f.subject): f for f in fs if f.severity == "error"}
    assert ("R2.operating-window", "mid-031") in errs
    assert ("R7.element-balance", "high-031") in errs
    f = errs[("R7.element-balance", "high-031")]
    assert f.file == "data/runs.csv"
    line = (leach / "data/runs.csv").read_text().splitlines()[f.line - 1]
    assert line.startswith("high-031")


def test_exclusions_need_reasons_and_downgrade(leach):
    prj = project.load(leach)
    fs = project.validate(prj)
    assert not [f for f in fs if f.severity == "error"]
    assert any(f.id == "data.excluded" for f in fs)
    prj.manifest["data"]["exclude"] = [{"run": "mid-031"}]
    assert any(f.id == "data.exclude-reason" for f in project.validate(prj))


def test_scope_boundary_contradiction(leach):
    prj = project.load(leach)
    prj.scope["boundary"] = "cradle-to-gate"
    assert any(f.id == "scope.boundary" and f.severity == "error" for f in project.validate(prj))
