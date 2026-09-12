from __future__ import annotations

import html
import os
import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image

from .model import Guide

TEMPLATES = Path(__file__).parent / "templates"

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def _instruction_html(text: str) -> str:
    parts = html.escape(text).split("`")
    for i in range(1, len(parts), 2):
        parts[i] = f"<code>{parts[i]}</code>"
    return "".join(parts)


def _overlay_style(a, width: int, height: int) -> str:
    def pct(value: int, total: int) -> str:
        return f"{value / total * 100:.3f}%"

    if a.type == "box":
        return (
            f"left:{pct(a.x, width)};top:{pct(a.y, height)};"
            f"width:{pct(a.w, width)};height:{pct(a.h, height)};"
        )
    return f"left:{pct(a.x, width)};top:{pct(a.y, height)};"


def _find_chrome() -> Path:
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return Path(candidate)
    for name in ("google-chrome", "chromium", "chrome"):
        found = shutil.which(name)
        if found:
            return Path(found)
    raise RuntimeError(
        "no headless-capable Chromium found; install Google Chrome or set "
        "CHROME_PATH"
    )


def export_html(guide: Guide, project_dir: Path, out_dir: Path) -> Path:
    project_dir = Path(project_dir)
    out_dir = Path(out_dir)
    frames_out = out_dir / "frames"
    frames_out.mkdir(parents=True, exist_ok=True)

    sections = []
    number = 0
    for section in guide.sections:
        steps = []
        for step in section.steps:
            number += 1
            src = project_dir / step.frame
            shutil.copy(src, frames_out / Path(step.frame).name)
            with Image.open(src) as img:
                width, height = img.size
            steps.append(
                {
                    "number": number,
                    "width": width,
                    "height": height,
                    "frame_src": f"frames/{Path(step.frame).name}",
                    "instruction_html": _instruction_html(step.instruction),
                    "overlays": [
                        {
                            "cls": f"ann-{'box' if a.type == 'box' else 'text'}",
                            "style": _overlay_style(a, width, height),
                            "text": html.escape(a.text) if a.text else None,
                        }
                        for a in step.annotations
                    ],
                }
            )
        sections.append({"title": html.escape(section.title), "steps": steps})

    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=False)
    template = env.get_template("guide.html.j2")
    rendered = template.render(guide={"title": html.escape(guide.title)}, sections=sections)
    out_path = out_dir / "guide.html"
    out_path.write_text(rendered, encoding="utf-8")
    return out_path


def export_pdf(html_path: Path, pdf_path: Path, chrome: Path | None = None) -> Path:
    html_path = Path(html_path)
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    chrome_env = os.environ.get("CHROME_PATH")
    chrome = Path(chrome_env) if chrome_env else (chrome or _find_chrome())
    subprocess.run(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            f"--print-to-pdf={pdf_path}",
            "--no-pdf-header-footer",
            html_path.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
    )
    if not pdf_path.exists():
        raise RuntimeError(f"chrome did not produce {pdf_path}")
    return pdf_path
