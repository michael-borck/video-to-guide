from __future__ import annotations

import html
import math
import os
import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .model import Annotation, Guide

TEMPLATES = Path(__file__).parent / "templates"

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _instruction_html(text: str) -> str:
    parts = html.escape(text).split("`")
    for i in range(1, len(parts), 2):
        parts[i] = f"<code>{parts[i]}</code>"
    return "".join(parts)


def _load_font(size: int):
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _line_width(img: Image.Image) -> int:
    return max(3, img.height // 250)


def _default_text_size(img: Image.Image) -> int:
    return max(16, img.height // 30)


def _apply_redact(img: Image.Image, a: Annotation) -> None:
    x, y, w, h = a.x, a.y, a.w or 0, a.h or 0
    if w <= 0 or h <= 0:
        return
    if a.mode == "solid":
        ImageDraw.Draw(img).rectangle([x, y, x + w, y + h], fill=(17, 17, 17))
        return
    region = img.crop((x, y, x + w, y + h))
    if a.mode == "pixelate":
        block = max(12, min(w, h) // 10)
        small = region.resize((max(1, w // block), max(1, h // block)), Image.NEAREST)
        region = small.resize((w, h), Image.NEAREST)
    else:
        region = region.filter(ImageFilter.GaussianBlur(16))
    img.paste(region, (x, y))


def _draw_arrow(draw: ImageDraw.ImageDraw, a: Annotation, lw: int) -> None:
    color = a.color or "#e53e3e"
    ex, ey = a.x + (a.w or 0), a.y + (a.h or 0)
    draw.line([a.x, a.y, ex, ey], fill=color, width=lw)
    head = max(lw * 4, 14)
    angle = math.atan2(ey - a.y, ex - a.x)
    spread = math.radians(155)
    p1 = (ex + head * math.cos(angle + spread), ey + head * math.sin(angle + spread))
    p2 = (ex + head * math.cos(angle - spread), ey + head * math.sin(angle - spread))
    draw.polygon([(ex, ey), p1, p2], fill=color)


def _draw_text(draw: ImageDraw.ImageDraw, a: Annotation) -> None:
    size = a.size or 24
    font = _load_font(size)
    text = a.text or ""
    left, top, right, bottom = draw.textbbox((a.x, a.y), text, font=font)
    pad = size // 5
    draw.rectangle(
        [left - pad, top - pad // 2, right + pad, bottom + pad // 2],
        fill=(255, 255, 255, 235),
        outline=(203, 213, 224),
    )
    draw.text((a.x, a.y), text, fill=a.color or "#1a202c", font=font)


def _flatten(src: Path, annotations: list[Annotation]) -> Image.Image:
    img = Image.open(src).convert("RGB")
    for a in annotations:
        if a.type == "redact":
            _apply_redact(img, a)

    draw = ImageDraw.Draw(img)
    lw = _line_width(img)
    for a in annotations:
        if a.type == "box":
            draw.rectangle(
                [a.x, a.y, a.x + (a.w or 0), a.y + (a.h or 0)],
                outline=a.color or "#e53e3e",
                width=lw,
            )
        elif a.type == "arrow":
            _draw_arrow(draw, a, lw)
        elif a.type == "text":
            _draw_text(draw, a)
    return img


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
            baked = _flatten(src, step.annotations)
            baked.save(frames_out / Path(step.frame).name)
            steps.append(
                {
                    "number": number,
                    "width": baked.width,
                    "height": baked.height,
                    "frame_src": f"frames/{Path(step.frame).name}",
                    "instruction_html": _instruction_html(step.instruction),
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
