# Video-to-Guide App — Build Spec

Turn a screen recording (e.g. from Screen Studio) into a step-by-step guide:
extract candidate frames → pick & annotate in a WebUI → group into sections →
export as HTML and PDF.

---

## 1. Goal

Input: a video file (mp4).
Output: a structured, shareable guide with:
- Sections (titled groups of steps)
- Steps (a frame image + instruction text + optional annotations)
- Exported as both a standalone HTML doc and a PDF

Primary use case: turning a recorded tutorial into a written walkthrough for
students, without re-doing the whole thing by hand.

---

## 2. Architecture Overview

```
video.mp4
   │
   ▼
[Backend: frame extraction]  (ffmpeg / PySceneDetect)
   │  → pool of candidate frame images + timestamps
   ▼
[WebUI: selection + annotation]
   │  - scrub video, browse candidate filmstrip
   │  - pick frames, add text/drawings, group into sections
   │  → guide.json (source of truth)
   ▼
[Export: HTML + PDF]  (Jinja2 template → same HTML rendered to PDF)
   │
   ▼
guide.html + guide.pdf
```

Key principle: **one JSON model, one HTML template**, render PDF from that
same HTML (via headless browser) instead of building PDF layout separately.
Keeps HTML and PDF visually consistent for free.

---

## 3. Stack

| Layer | Choice | Why |
|---|---|---|
| Frame extraction | `ffmpeg` (scene-change filter) or `PySceneDetect` | Mature, scriptable, no ML needed for v1 |
| Backend/API | Python + FastAPI | Simple, good for file handling + serving frames |
| Frontend | React (Vite) or plain HTML/JS if you want to skip build tooling | Canvas-based annotation needs some JS either way |
| Data model | JSON file per project | No DB needed for v1, human-readable, easy to version |
| HTML render | Jinja2 template | One template drives both HTML output and PDF source |
| PDF export | Headless Chromium (Puppeteer/Playwright) *or* WeasyPrint on the HTML | Reuses the HTML/CSS instead of a second layout system |

You can swap React for plain JS + `<canvas>` if you want to avoid a frontend
build step entirely and just open `index.html` locally during dev.

---

## 4. Data Model (`guide.json`)

```json
{
  "title": "How to set up your dev environment",
  "sections": [
    {
      "id": "sec-1",
      "title": "Installing dependencies",
      "steps": [
        {
          "id": "step-1",
          "timestamp": 12.4,
          "frame": "frames/frame_0001.png",
          "instruction": "Open a terminal and run `npm install`.",
          "annotations": [
            { "type": "box", "x": 100, "y": 200, "w": 300, "h": 80 },
            { "type": "text", "x": 120, "y": 190, "text": "Run this command" }
          ]
        }
      ]
    }
  ]
}
```

Keep annotation coordinates relative to the original frame's pixel
dimensions, not the on-screen render size, so scaling is just a CSS/print
concern later, not a data problem.

---

## 5. Pipeline Steps

### 5.1 Frame extraction (backend, run once per video)

- Scene-change detection to generate a shortlist of candidate frames:
  ```
  ffmpeg -i video.mp4 -vf "select='gt(scene,0.3)',showinfo" -vsync vfr frames/frame_%04d.png
  ```
- Also store each frame's timestamp (parse from `showinfo` output or use
  `PySceneDetect` which gives you timestamps directly).
- This is a *shortlist*, not the final selection — the WebUI lets the user
  browse/scrub and capture any frame, not just the candidates.

### 5.2 WebUI: browse + select

- Video player with scrubber.
- Filmstrip of candidate frames below the player; click to jump to that
  timestamp.
- "Capture this frame" button grabs the current paused frame even if it's
  not in the candidate list (covers moments scene-detection missed).
- Selected frames get added to a working list.

### 5.3 WebUI: annotate

- Each selected frame opens in a canvas editor.
- v1 scope: text box overlay only (fastest to build, often enough).
- v1.5 scope: arrows/boxes (rect + arrow tool, drag to draw).
- Store annotations as simple shape objects (see data model above), not
  baked into the image — keeps them editable later.

### 5.4 WebUI: organize

- Group steps into sections with titles.
- Drag-to-reorder steps within a section and across sections.
- Edit instruction text per step.

### 5.5 Export

- Render `guide.json` through the Jinja2 HTML template → `guide.html`.
- Render the same HTML through headless Chromium (or WeasyPrint) →
  `guide.pdf`.
- Print-specific CSS (`@media print`) handles page breaks per section/step.

---

## 6. Build Order (suggested)

1. **Skip the UI at first.** Write the ffmpeg extraction script standalone,
   confirm it produces sane frames + timestamps for a real Screen Studio
   export.
2. **Hand-write a `guide.json`** for one test video, and get the Jinja2 →
   HTML → PDF export pipeline working end-to-end. This proves the export
   half independent of any UI.
3. **Build the WebUI selection screen**: video player + filmstrip + "add to
   guide" button, writing directly to `guide.json` via a simple API.
4. **Add the annotation canvas** (text boxes first, drawing tools after).
5. **Add section grouping + reordering.**
6. **Polish print CSS** for the PDF output last, once content structure is
   stable.

This order gets you an end-to-end working pipeline (even if manual/ugly)
before investing in UI polish — steps 1–2 alone give you something usable
via hand-edited JSON.

---

## 7. Nice-to-haves (post-v1)

- Auto-suggest instruction text from an OCR pass or from nearby audio
  transcript (if the source video has narration).
- Smarter frame selection (dedupe visually-similar candidates).
- Themes/branding for the exported HTML/PDF.
- Multi-video guides (stitch steps from more than one recording).

---

## 8. Known Fiddly Bits (budget time for these)

- **Print CSS**: page breaks, image scaling, margins — always takes longer
  than expected. Save for last, once content is stable.
- **Annotation UX**: resizable/draggable shapes on canvas feel simple but
  eat time to get right. Start with static text boxes; add drag/resize
  later.
- **Coordinate scaling**: keep annotation coordinates in original-image
  pixel space, convert to display scale only at render time (both in the
  editor and in the HTML/PDF template), or you'll get drift between what
  you drew and what exports.

---

## 9. Minimal File Layout

```
video-to-guide/
├── backend/
│   ├── extract_frames.py      # ffmpeg/PySceneDetect wrapper
│   ├── main.py                 # FastAPI app: upload video, serve frames, save guide.json
│   └── templates/
│       └── guide.html.j2       # Jinja2 template, drives both HTML + PDF
├── frontend/
│   ├── src/
│   │   ├── VideoPicker.jsx
│   │   ├── FrameEditor.jsx     # canvas annotation
│   │   └── SectionOrganizer.jsx
│   └── ...
├── projects/
│   └── <project-name>/
│       ├── video.mp4
│       ├── frames/
│       └── guide.json
└── exports/
    └── <project-name>/
        ├── guide.html
        └── guide.pdf
```

---

## 10. Open Decision: Build vs. Fork vs. Reuse

Category name for this space: **workflow documentation tool** / **user guide
creation tool** (same category as Tango, Scribe, Guidde — but working from a
pre-recorded video rather than live click-capture).

There's at least one existing open-source project close to this:

**VideoDocGen** — `github.com/vocso-com/videodocgen`
- Converts demo/screen-recording videos into structured documentation: a
  Markdown "User Guide," extracted screenshots, and a structured
  `document.json`.
- Local-only: no cloud APIs, no network calls at runtime. Uses FFmpeg +
  PySceneDetect for extraction, Tesseract for OCR — same stack sketched in
  Section 3 above.
- Explicitly built to be extensible: OCR, understanding, rendering, and
  export are provider interfaces selected by config, so new implementations
  slot in without rework.
- Not yet on PyPI; install from source (easy to fork and hack on directly).
- Likely gap vs. what's wanted here: sounds like it auto-generates the
  guide text/structure from the video (OCR + scene detection driving
  content) rather than giving a human an interactive WebUI to pick frames
  and write instructions by hand. No confirmed section-grouping UI or PDF
  export path yet either — needs checking against the actual repo.

**Other lead (license caveat):** `video2doc` (kian98 on GitHub) — uses
OpenAI/Claude + Whisper for transcription-driven doc generation. Licensed
CC BY-NC-SA (non-commercial only), so only usable as reference/inspiration,
not as a base to fork from if this ever needs to be anything other than
personal/non-commercial use.

**Decision to make once the project is actually opened (do the deeper dive
then, not now):**
1. Read VideoDocGen's `ARCHITECTURE.md` and actual UI/output to see how
   close it really is.
2. Options, roughly in order of least-to-most effort:
   - **Fork and extend** — if its extraction/export pipeline already covers
     Sections 3 and 5 above, add only the missing piece: an interactive
     WebUI for manual frame selection, annotation, and section-grouping.
   - **Reuse parts** — take just the extraction script or the Jinja2/export
     approach, write the WebUI from scratch.
   - **Build from scratch** — if the automation-first design doesn't fit a
     human-in-the-loop workflow well enough to be worth untangling.
3. Whichever path is chosen, keep the `guide.json` data model (Section 4)
   as the interface boundary, so the WebUI and export logic stay decoupled
   from whichever extraction backend ends up in use.

---

## 11. Naming

Will likely live at `<product>.borck.education` or `<product>.borck.dev`,
so a clean top-level domain isn't a constraint. PyPI name availability is
still a nice-to-have (in case the extraction/export core is published as an
installable package separately from the WebUI).

Lean toward descriptive names tied to the category (**workflow
documentation tool** / **user guide creation**) rather than an abstract
brand — easier to search for, less likely to collide with unrelated
projects, and clearer at a glance what the tool does. Decide this once the
build-vs-fork decision above is settled, since forking an existing project
may mean inheriting (or deliberately renaming from) its existing name.
