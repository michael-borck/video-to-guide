from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from threading import Lock
from uuid import uuid4

import cv2
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from videotoguide.extract import extract_frames
from videotoguide.export import export_guide
from videotoguide.model import Guide, load_guide, resolve_frame, save_guide

# Defaults keep the source-checkout layout; the packaged desktop app sets
# VTG_ROOT (user data dir) and VTG_DIST (frontend assets inside the bundle).
ROOT = Path(os.environ.get("VTG_ROOT", Path(__file__).resolve().parents[1]))
PROJECTS = ROOT / "projects"
EXPORTS = ROOT / "exports"

app = FastAPI(title="video-to-guide")


@lru_cache(maxsize=None)
def project_lock(name: str):
    return Lock()


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
def extract(
    name: str,
    threshold: float = Query(27.0, gt=0),
    max_frames: int = Query(40, ge=1),
):
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
    return json.loads(manifest.read_text(encoding="utf-8"))


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
    try:
        for section in guide.sections:
            for step in section.steps:
                resolve_frame(directory, step.frame)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    with project_lock(name):
        save_guide(guide, directory / "guide.json")
    return guide


@app.post("/api/projects/{name}/suggestions")
def suggestions(name: str, model_size: str = "base"):
    directory = project_dir(name)
    video = directory / "video.mp4"
    if not video.exists():
        raise HTTPException(status_code=404, detail="no video.mp4 in project")
    try:
        from videotoguide.transcribe import suggestions_for_steps, transcribe_cached

        segments = transcribe_cached(video, model_size)
    except ImportError:
        raise HTTPException(
            status_code=400,
            detail="transcription extra not installed: uv sync --extra transcribe",
        )
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc

    with project_lock(name):
        guide_path = directory / "guide.json"
        guide = load_guide(guide_path) if guide_path.exists() else Guide(title=name)
        steps = [s for section in guide.sections for s in section.steps]
        texts = suggestions_for_steps(segments, steps)
        for step, text in zip(steps, texts):
            step.suggestions = [text] if text else []
        save_guide(guide, guide_path)
    return {"segments": len(segments), "guide": guide}


class CaptureRequest(BaseModel):
    timestamp: float = Field(ge=0, allow_inf_nan=False)


@app.post("/api/projects/{name}/capture")
def capture(name: str, body: CaptureRequest):
    directory = project_dir(name)
    video = directory / "video.mp4"
    if not video.exists():
        raise HTTPException(status_code=404, detail="no video.mp4 in project")
    frames_dir = directory / "frames"
    frames_dir.mkdir(exist_ok=True)

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="cannot open video")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(body.timestamp * fps))
    ok, img = cap.read()
    cap.release()
    if not ok:
        raise HTTPException(status_code=400, detail="cannot seek to timestamp")

    file = f"captured_{uuid4().hex}.png"
    if not cv2.imwrite(str(frames_dir / file), img):
        raise HTTPException(status_code=500, detail="cannot write captured frame")
    return {"file": f"frames/{file}", "timestamp": round(body.timestamp, 3)}


@app.post("/api/projects/{name}/export")
def export(name: str):
    directory = project_dir(name)
    with project_lock(name):
        if not (directory / "guide.json").exists():
            raise HTTPException(status_code=404, detail="save a guide before exporting")
        try:
            guide = load_guide(directory / "guide.json")
            html_path, pdf_path = export_guide(guide, directory, EXPORTS / name)
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
            raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc
    return {"html": str(html_path), "pdf": str(pdf_path)}


app.mount("/media", StaticFiles(directory=PROJECTS), name="media")
EXPORTS.mkdir(exist_ok=True)
app.mount("/exports", StaticFiles(directory=EXPORTS, html=True), name="exports")

DIST = Path(os.environ.get("VTG_DIST", ROOT / "frontend" / "dist"))
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="spa")
