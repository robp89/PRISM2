from click.testing import CliRunner
from fastapi.testclient import TestClient

from prism2.cli import main
from prism2.server import create_app


def test_cli_init_validate_design(tmp_path):
    r = CliRunner()
    res = r.invoke(main, ["init", str(tmp_path / "m"), "--title", "T"])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "m" / ".claude" / "skills" / "prism-model" / "SKILL.md").exists()
    res = r.invoke(main, ["validate", str(tmp_path / "m")])
    assert res.exit_code == 1 and "scope.yaml" in res.output  # goal missing
    res = r.invoke(main, ["design", str(tmp_path / "m"), "-n", "4"])
    assert res.exit_code == 0 and (tmp_path / "m" / "design" / "run-sheet.csv").exists()


def test_cli_validate_example(leach):
    res = CliRunner().invoke(main, ["validate", str(leach)])
    assert res.exit_code == 0, res.output
    assert "0 error(s)" in res.output


def test_server(leach, smelt):
    c = TestClient(create_app([leach.parent]))
    ps = {p["id"]: p for p in c.get("/api/projects").json()}
    assert set(ps) == {"leach-demo", "smelt-screening"}
    assert ps["smelt-screening"]["verdict"]["level"] == "Screening only"
    snap = c.get("/api/projects/leach-demo").json()
    assert snap["process"]["id"] == "bml-v1" and snap["n_runs"] == 93
    assert c.post("/api/projects/leach-demo/export").status_code == 409  # never built
    assert c.get("/api/projects/leach-demo/files/../prism.yaml").status_code == 404
    assert c.get("/app/").status_code == 200
    assert len(c.get("/api/library").json()) == 3
