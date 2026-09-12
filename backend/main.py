from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from videotoguide.extract import extract_frames
from videotoguide.export import export_html, export_pdf
from videotoguide.model import Guide, load_guide, save_guide

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects"
EXPORTS = ROOT / "exports"

app = FastAPI(title="video-to-guide")


def project_dir(name: str) -> Path:
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(status_code=400, detail="invalid project name")
    path = PROJECTS / name
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="project not found")
    return path


@app.get("/api/projects")
def list_projects() -> list[str]:
    if not PROJECTS.exists():
        return []
    return sorted(p.name for p in PROJECTS.iterdir() if p.is_dir())


@app.post("/api/projects/{name}/extract")
def extract(name: str, threshold: float = 27.0, max_frames: int = 40):
    directory = project_dir(name)
    video = directory / "video.mp4"
    if not video.exists():
        raise HTTPException(status_code=404, detail="no video.mp4 in project")
    result = extract_frames(video, scene_threshold=threshold, max_frames=max_frames)
    return result


@app.get("/api/projects/{name}/frames")
def frames(name: str):
    directory = project_dir(name)
    manifest = directory / "frames" / "manifest.json"
    if not manifest.exists():
        raise HTTPException(status_code=404, detail="not extracted yet")
    return manifest.read_text(encoding="utf-8")


@app.get("/api/projects/{name}/guide")
def get_guide(name: str) -> Guide:
    directory = project_dir(name)
    path = directory / "guide.json"
    if not path.exists():
        return Guide(title=directory.name)
    return load_guide(path)


@app.put("/api/projects/{name}/guide")
def put_guide(name: str, guide: Guide) -> Guide:
    directory = project_dir(name)
    save_guide(guide, directory / "guide.json")
    return guide


@app.post("/api/projects/{name}/export")
def export(name: str):
    directory = project_dir(name)
    guide = load_guide(directory / "guide.json")
    out_dir = EXPORTS / name
    html_path = export_html(guide, directory, out_dir)
    pdf_path = export_pdf(html_path, out_dir / "guide.pdf")
    return {"html": str(html_path), "pdf": str(pdf_path)}


app.mount("/media", StaticFiles(directory=PROJECTS), name="media")
