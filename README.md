# video-to-guide

Turn a screen recording into a step-by-step guide: extract candidate frames,
pick & annotate in a web UI, group into sections, export as HTML and PDF.

Working name — will be renamed before any PyPI publish. Spec:
`video-to-guide-app-spec.md`.

## Layout

```
src/videotoguide/   core package: data model, frame extraction, HTML/PDF export
backend/            FastAPI app (thin wrapper over the core)
projects/<name>/    video.mp4, frames/, guide.json
exports/<name>/     guide.html, guide.pdf (generated)
```

## Setup

```bash
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/video-to-guide"
uv sync
```

The venv lives off-repo because this project sits on an exFAT volume, which
breaks Python virtual environments.

PDF export needs Chrome (or Chromium/Edge); it is found automatically, or
set `CHROME_PATH`.

## Try the pipeline (no UI needed)

```bash
uv run vtg extract projects/demo
uv run vtg export projects/demo
open exports/demo/guide.html
```

`vtg extract` accepts a video file or a project directory (uses
`video.mp4` inside it).

## Run the app

Build the frontend once, then serve everything from FastAPI:

```bash
cd frontend && npm install && npm run build && cd ..
uv run uvicorn backend.main:app
```

Open http://127.0.0.1:8000, pick a project, scrub the video, capture frames
into the guide, then Export.

For frontend development with hot reload:

```bash
uv run uvicorn backend.main:app
cd frontend && npm run dev
```

The Vite dev server proxies `/api`, `/media`, and `/exports` to the backend.

## Status

Early scaffold. Frame extraction and HTML/PDF export work end to end via the
CLI; the web UI (frame picking, annotation, section organizing) is not built
yet. See `video-to-guide-app-spec.md` for the plan.

## Acknowledgments

- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) drives scene
  detection; OpenCV handles frames and the Laplacian-variance sharpness
  scoring.
- [VideoDocGen](https://pypi.org/project/videodocgen/) (MIT) inspired two
  extraction ideas used here: picking the sharpest frame per scene and
  perceptual-hash dedup. This project borrows the techniques, not the code.
- [video2doc](https://github.com/kian98/video2doc) is prior art in
  video-to-documentation (CC BY-NC-SA, so reference only).
- Built on FastAPI, Jinja2, imagehash, Pillow, and ffmpeg.

## License

[MIT](LICENSE)

