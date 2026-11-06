"""The viewer's API: one model repository or a folder of them, read from the files in git.

Read endpoints never change files. ``POST .../build`` and ``POST .../export`` write only to the
repository's build/ folder, as the CLI does; start with ``read_only=True`` to disable them.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, build, library, project

VIEWER = Path(__file__).parent / "viewer"


def discover(paths: list[Path]) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for p in paths:
        p = p.resolve()
        cands = [p] if (p / project.MANIFEST).exists() else sorted(c for c in p.iterdir() if (c / project.MANIFEST).exists())
        for c in cands:
            try:
                found[project.load(c).id] = c
            except Exception:  # noqa: BLE001 - a broken repo should not take the viewer down
                found[c.name] = c
    return found


def create_app(paths: list[Path], read_only: bool = False) -> FastAPI:
    app = FastAPI(title="PRISM2", version=__version__)
    repos = discover(paths)

    def get(pid: str) -> project.Project:
        if pid not in repos:
            raise HTTPException(404, f"no model repository {pid!r}")
        return project.load(repos[pid])

    @app.get("/api/version")
    def version():
        return {"prism": __version__, "api": "1"}

    @app.get("/api/projects")
    def projects():
        out = []
        for pid, root in repos.items():
            try:
                s = build.snapshot(project.load(root))
                out.append({"id": pid, "title": s["title"], "process": {"id": s["process"]["id"], "title": s["process"]["title"], "status": s["process"]["status"]},
                            "origin": s["origin"], "n_runs": s["n_runs"], "verdict": s["verdict"], "tier": s["certification"]["tier"],
                            "stale": bool(s["stale"]), "built_at": s["built_at"]})
            except Exception as e:  # noqa: BLE001
                out.append({"id": pid, "title": pid, "error": str(e)})
        return out

    @app.get("/api/projects/{pid}")
    def snapshot(pid: str):
        return build.snapshot(get(pid))

    @app.post("/api/projects/{pid}/build")
    def do_build(pid: str, demo: bool = False):
        if read_only:
            raise HTTPException(403, "viewer is read-only: run `prism build`")
        prj = get(pid)
        build.run(prj, demo=demo, n_mc=500)
        return build.snapshot(project.load(prj.root))

    @app.post("/api/projects/{pid}/export")
    def do_export(pid: str, demo: bool = False):
        if read_only:
            raise HTTPException(403, "viewer is read-only: run `prism export xycle`")
        try:
            return build.export_xycle(get(pid), demo=demo)
        except build.ExportRefused as e:
            raise HTTPException(409, {"refused": e.blockers}) from None

    @app.get("/api/projects/{pid}/files/{path:path}")
    def file(pid: str, path: str):
        prj = get(pid)
        f = (prj.build_dir / path).resolve()
        if not f.is_relative_to(prj.build_dir.resolve()) or not f.is_file():
            raise HTTPException(404, "not found")
        return FileResponse(f, filename=f.name)

    @app.get("/api/library")
    def lib():
        return [t.summary() for t in library.list_types()]

    @app.get("/")
    def index():
        return RedirectResponse("/app/")

    app.mount("/app", StaticFiles(directory=VIEWER, html=True), name="viewer")
    return app
