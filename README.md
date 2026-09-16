# video-to-guide

Turn a screen recording into a step-by-step guide: extract candidate frames,
pick & annotate in a web UI, group into sections, export as HTML and PDF.

On PyPI as [`videotoguide`](https://pypi.org/project/videotoguide/).
Desktop installers and screenshots: the
[project page](https://michael-borck.github.io/video-to-guide/). Spec:
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

Exports use a dedicated output directory, separate from the source project.
Each successful export replaces that directory, including its images, so removed
steps do not leave old screenshots behind. If HTML or PDF generation fails, the
previous export stays intact. Frame paths in `guide.json` must stay inside the
project's `frames/` directory.

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

Edits save in order. The editor displays failed saves and provides a retry button;
project switching waits for successful saves. Export waits for pending edits too.

## Suggested text from narration (optional)

```bash
uv sync --extra transcribe
```

Then use "Suggest from audio" in the app (or
`POST /api/projects/<name>/suggestions`). Transcription runs locally via
[faster-whisper](https://github.com/SYSTRAN/faster-whisper); the model
downloads on first use and the transcript caches to
`projects/<name>/transcript.json`. Narration between two frames becomes a
suggestion on the earlier step — accept it or ignore it. Steps always stay
human-editable.

## Tests

Backend regression tests use the standard-library test runner. `uv sync` installs
the development HTTP client needed by FastAPI's test client.

```bash
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/video-to-guide"
uv sync
uv run python -m unittest discover -s tests -v
```

Frontend tests need Node.js 22.12 or newer:

```bash
cd frontend
npm install
npm test
npm run build
```

The tests cover project switching, save ordering and retry, capture readiness,
suggestion acceptance, frame selection, path validation, redaction isolation,
and export replacement. PDF failure tests mock Chrome; actual PDF export still
requires an installed Chromium browser.

## Desktop app (Tauri)

The desktop app is a Tauri shell that spawns the FastAPI server, built by
PyInstaller into a self-contained sidecar, on a free localhost port and points
the webview at it. Projects and exports live in the user's application-data
directory (`~/Library/Application Support/video-to-guide` on macOS).

Releases are built by [.github/workflows/release.yml](.github/workflows/release.yml)
on tag push (`v*`): it re-runs the tests, builds the frontend, builds the
sidecar for the runner platform, then `tauri-action` uploads installers to a
draft release, published as "Latest" once every platform succeeds. The landing
page under `docs/` (served by GitHub Pages) detects the visitor's platform and
links the matching installer.

Build it locally (macOS/Linux, Windows similar):

```bash
npm --prefix frontend run build
uv sync --group package
uv run pyinstaller --noconfirm vtg-server.spec
mkdir -p src-tauri/sidecar && cp -r dist/vtg-server src-tauri/sidecar/
cargo tauri build   # or: cargo run from src-tauri for a debug shell
```

Regenerate app icons after changing the drawing in
`scripts/generate_icons.py`.

## Status

The CLI and web UI support frame capture, annotation, section organizing, local
transcription suggestions, and HTML/PDF export. See `video-to-guide-app-spec.md`
for the remaining plans.

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
