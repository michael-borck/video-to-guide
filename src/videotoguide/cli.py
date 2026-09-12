from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .export import export_html, export_pdf
from .extract import extract_frames
from .model import load_guide


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vtg", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="extract candidate frames from a video")
    p_extract.add_argument("target", type=Path, help="video file or project directory")
    p_extract.add_argument("--out", type=Path, default=None)
    p_extract.add_argument("--threshold", type=float, default=27.0)
    p_extract.add_argument("--max-frames", type=int, default=40)

    p_export = sub.add_parser("export", help="render a project's guide.json to HTML + PDF")
    p_export.add_argument("project", type=Path, help="directory containing guide.json")
    p_export.add_argument("--out", type=Path, default=None)

    args = parser.parse_args(argv)

    if args.command == "extract":
        target = args.target
        if target.is_dir():
            video = target / "video.mp4"
            if not video.exists():
                print(f"no video.mp4 in {target}", file=sys.stderr)
                return 1
        else:
            video = target
        result = extract_frames(
            video,
            out_dir=args.out,
            scene_threshold=args.threshold,
            max_frames=args.max_frames,
        )
        frames_dir = args.out or video.parent / "frames"
        print(f"{len(result.frames)} frames -> {frames_dir}")
        for f in result.frames:
            print(f"  {f.file}  t={f.timestamp:>8.2f}s  sharpness={f.sharpness}")
        return 0

    if args.command == "export":
        guide = load_guide(args.project / "guide.json")
        out_dir = args.out or Path("exports") / args.project.name
        html_path = export_html(guide, args.project, out_dir)
        pdf_path = export_pdf(html_path, out_dir / "guide.pdf")
        print(f"{html_path}\n{pdf_path}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
