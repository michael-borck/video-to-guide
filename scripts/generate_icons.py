"""Generate the Tauri app icon set from a simple vector-ish drawing.

Usage: uv run python scripts/generate_icons.py
Writes PNGs into src-tauri/icons/; run `iconutil -c icns` afterwards on
macOS for icon.icns (script does it when available).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path("src-tauri/icons")
SIZE = 1024
BG = (30, 41, 59, 255)  # slate-800
ACCENT = (245, 158, 11, 255)  # amber-500
FG = (241, 245, 249, 255)  # slate-100


def rounded_bg(draw: ImageDraw.ImageDraw) -> None:
    radius = SIZE // 5
    draw.rounded_rectangle([0, 0, SIZE, SIZE], radius=radius, fill=BG)


def play_triangle(draw: ImageDraw.ImageDraw) -> None:
    # Left half: a play glyph centred in a circle-free zone.
    cx, cy = SIZE * 0.38, SIZE * 0.5
    r = SIZE * 0.16
    pts = [(cx - r * 0.8, cy - r), (cx - r * 0.8, cy + r), (cx + r * 1.1, cy)]
    draw.polygon(pts, fill=ACCENT)


def step_lines(draw: ImageDraw.ImageDraw) -> None:
    # Right half: three ascending "guide steps".
    x0 = SIZE * 0.58
    ys = [SIZE * 0.36, SIZE * 0.5, SIZE * 0.64]
    height = SIZE * 0.045
    for i, y in enumerate(ys):
        draw.rounded_rectangle(
            [x0, y, SIZE * (0.82 + 0.06 * i), y + height],
            radius=height / 2,
            fill=FG,
        )


def build_master() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    rounded_bg(draw)
    play_triangle(draw)
    step_lines(draw)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master = build_master()

    pngs = {
        "32x32.png": 32,
        "128x128.png": 128,
        "128x128@2x.png": 256,
        "icon.png": 512,
    }
    for name, size in pngs.items():
        master.resize((size, size), Image.LANCZOS).save(OUT / name)

    # macOS iconset -> icns
    iconset = OUT / "icon.iconset"
    iconset.mkdir(exist_ok=True)
    for base, size in [(16, 16), (32, 32), (128, 128), (256, 256), (512, 512)]:
        master.resize((size, size), Image.LANCZOS).save(iconset / f"icon_{base}x{base}.png")
        master.resize((size * 2, size * 2), Image.LANCZOS).save(
            iconset / f"icon_{base}x{base}@2x.png"
        )
    try:
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(OUT / "icon.icns")],
            check=True,
        )
    except FileNotFoundError:
        print("iconutil not found; skip icon.icns (build on macOS)")

    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master.resize((256, 256), Image.LANCZOS).save(
        OUT / "icon.ico", sizes=ico_sizes
    )
    print(f"icons written to {OUT}")


if __name__ == "__main__":
    main()
