"""The ``prism`` command line."""
from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path

import click

from . import __version__, build as pipeline, doe, library, project
from .findings import summarise

TEMPLATES = Path(__file__).parent / "templates"
SKILLS = Path(__file__).parent / "skills"


def _load(path: str) -> project.Project:
    try:
        return project.load(path)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from None


@click.group()
@click.version_option(__version__, prog_name="prism")
def main() -> None:
    """PRISM2: life cycle inventory as code. Checks run, models fit and inventories build from plain files in git."""


@main.command()
@click.argument("directory")
@click.option("--title", default=None, help="Model title.")
@click.option("--process-type", "ptype", default="bml-v1", show_default=True, help="Library id of the process type.")
def init(directory: str, title: str | None, ptype: str) -> None:
    """Create a new PRISM model repository with agent skills."""
    root = Path(directory)
    if root.exists() and any(root.iterdir()):
        raise click.ClickException(f"{root} exists and is not empty")
    pt = library.resolve(ptype)
    shutil.copytree(TEMPLATES / "project", root, dirs_exist_ok=True)
    m = (root / "prism.yaml").read_text()
    m = m.replace("{{id}}", root.name).replace("{{title}}", title or root.name).replace("{{process_type}}", pt.id)
    m = m.replace("{{targets}}", ", ".join(pt.outputs))
    (root / "prism.yaml").write_text(m)
    fu = pt.data.get("functional_unit", {})
    s = (root / "scope.yaml").read_text().replace("{{functional_unit}}", f"{fu.get('amount')} {fu.get('unit')} {fu.get('of')}")
    (root / "scope.yaml").write_text(s)
    keys = [k for k in pt.fields] + list(pt.outputs) + list(pt.assays)
    with (root / "data" / "runs.csv").open("w", newline="") as fh:
        csv.writer(fh).writerow(["run_id", "grade"] + keys)
    _install_skills(root)
    click.echo(f"created {root} ({pt.title}). Next: fill scope.yaml and feedstocks.yaml, add runs to data/runs.csv, then `prism validate`.")


def _install_skills(root: Path) -> None:
    dest = root / ".claude" / "skills"
    dest.mkdir(parents=True, exist_ok=True)
    for d in SKILLS.iterdir():
        if d.is_dir():
            shutil.copytree(d, dest / d.name, dirs_exist_ok=True)
    shutil.copy(SKILLS / "AGENTS.md", root / "AGENTS.md")
    (root / "CLAUDE.md").write_text("@AGENTS.md\n")


@main.group()
def skills() -> None:
    """Agent skills in a model repository."""


@skills.command("update")
@click.argument("path", default=".")
def skills_update(path: str) -> None:
    """Refresh the agent skills (.claude/skills, AGENTS.md) in a model repository."""
    _load(path)
    _install_skills(Path(path))
    click.echo("skills updated")


@main.command()
@click.argument("path", default=".")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.option("--all", "show_all", is_flag=True, help="Also list passing rule results.")
def validate(path: str, as_json: bool, show_all: bool) -> None:
    """Check every file; print findings as file:line with stable ids. Exit 1 on errors."""
    prj = _load(path)
    fs = project.validate(prj, include_pass=show_all)
    if as_json:
        click.echo(json.dumps([f.to_dict() for f in fs], indent=1))
    else:
        for f in fs:
            click.echo(f.format())
        c = summarise(fs)
        click.echo(f"\n{len(prj.runs)} runs, process type {prj.process.id} ({prj.process.status}): "
                   f"{c['error']} error(s), {c['warning']} warning(s), {c['skipped']} skipped")
    sys.exit(1 if any(f.severity == "error" for f in fs) else 0)


@main.command("build")
@click.argument("path", default=".")
@click.option("--demo", is_flag=True, help="Lift the synthetic-data and draft-type blockers; exports are watermarked.")
@click.option("--family", "families", multiple=True, type=click.Choice(["polynomial", "ann", "gp"]), help="Restrict model families.")
@click.option("--mc", default=1000, show_default=True, help="Monte Carlo samples per grade.")
def build_cmd(path: str, demo: bool, families: tuple, mc: int) -> None:
    """Fit and benchmark models, certify, generate the inventory and method note into build/."""
    prj = _load(path)
    r = pipeline.run(prj, demo=demo, families=list(families) or None, n_mc=mc)
    _print_verdict(r["verdict"], r["certification"])
    if r["model"]:
        click.echo("\nModels (held-out):")
        for t, res in r["model"]["targets"].items():
            fams = "  ".join(f"{f} R²={v['holdout']['r2']:.3f}" for f, v in res["families"].items())
            click.echo(f"  {t:<22} chosen {res['chosen']:<10} {fams}")
    click.echo(f"\nwrote {prj.rel(prj.build_dir)}/ (findings, model, certification, inventory, method-note.md, prism.lock.json)")


def _print_verdict(v: dict, cert: dict) -> None:
    click.echo(f"{v['level'].upper()}: {v['headline']}  (tier {cert['tier']})")
    for q in v["questions"]:
        click.echo(f"  {q['q']:<38} {q['a']:<8} {q['why']}")
    click.echo(f"  next: {v['next_action']}")
    if cert["blockers"]:
        click.echo("  export blocked: " + "; ".join(cert["blockers"]))


@main.command()
@click.argument("path", default=".")
def status(path: str) -> None:
    """The verdict card and whether build/ is up to date with the inputs."""
    prj = _load(path)
    snap = pipeline.snapshot(prj)
    _print_verdict(snap["verdict"], snap["certification"])
    if snap["stale"]:
        click.echo("  outdated: " + ", ".join(snap["stale"]) + " changed since the last build: run `prism build`")
    else:
        click.echo(f"  build up to date ({snap['built_at']})")


@main.command()
@click.argument("path", default=".")
@click.option("-n", "n_per_grade", default=16, show_default=True, help="Runs per feedstock grade.")
@click.option("--method", type=click.Choice(["sobol", "lhs"]), default="sobol", show_default=True)
@click.option("-o", "out", default="design/run-sheet.csv", show_default=True)
def design(path: str, n_per_grade: int, method: str, out: str) -> None:
    """Write a space-filling run sheet over the operating window and feedstock grades, and report coverage."""
    prj = _load(path)
    rows = doe.generate(prj, n_per_grade, method)
    dest = Path(path) / out
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    cov = doe.coverage(prj)
    click.echo(f"wrote {out}: {len(rows)} runs ({method}) to execute in the simulator or plant")
    click.echo(f"coverage of existing runs: {cov['share'] * 100:.0f}%" + (f"; gaps: {', '.join(cov['gaps'])}" if cov["gaps"] else ""))


@main.group()
def export() -> None:
    """Export files for other tools."""


@export.command("xycle")
@click.argument("path", default=".")
@click.option("--demo", is_flag=True, help="Allow synthetic data and draft process types; files are watermarked -DEMO.")
@click.option("--grade", default=None, help="Feedstock grade for the parameter point (default mid).")
def export_xycle(path: str, demo: bool, grade: str | None) -> None:
    """XYCLE Parameter Import (.csv), Model Import (.xlsx) and a draft DPP block. Fails closed."""
    prj = _load(path)
    try:
        r = pipeline.export_xycle(prj, demo=demo, grade=grade)
    except pipeline.ExportRefused as e:
        raise click.ClickException(str(e)) from None
    for f in r["files"]:
        click.echo(f"wrote {f}")
    for n in r["notes"]:
        click.echo(f"note: {n}")
    if r["watermark"]:
        click.echo("DEMO export: watermarked, not for use")


@main.group("library")
def library_grp() -> None:
    """The process library."""


@library_grp.command("list")
def library_list() -> None:
    for pt in library.list_types():
        flag = " (placeholder)" if pt.data.get("placeholder") else ""
        click.echo(f"{pt.id:<22} {pt.status:<9} {pt.title}{flag}")


@library_grp.command("check")
@click.argument("files", nargs=-1)
def library_check(files: tuple) -> None:
    """Check process-type files (default: the whole library). Exit 1 on errors."""
    paths = [Path(f) for f in files] or library.library_paths()
    bad = False
    for p in paths:
        fs = library.check_process_type(library.load_process_type(p), str(p))
        for f in fs:
            click.echo(f.format())
        bad |= any(f.severity == "error" for f in fs)
    sys.exit(1 if bad else 0)


@main.command()
@click.argument("paths", nargs=-1)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8765, show_default=True)
def serve(paths: tuple, host: str, port: int) -> None:
    """Serve the viewer and read-only API for one model repository or a folder of them."""
    try:
        import uvicorn

        from .server import create_app
    except ImportError:
        raise click.ClickException("install the serve extra: pip install 'prism2[serve]'") from None
    app = create_app([Path(p) for p in (paths or (".",))])
    click.echo(f"PRISM2 viewer on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
