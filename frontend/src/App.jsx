import React, { useEffect, useImperativeHandle, useRef, useState } from "react";
import VideoPicker from "./VideoPicker.jsx";
import SectionOrganizer from "./SectionOrganizer.jsx";
import Annotator from "./Annotator.jsx";
import { createSaveQueue, requestJson } from "./api.js";

export default function App() {
  const [projects, setProjects] = useState([]);
  const [project, setProject] = useState("");
  const [locked, setLocked] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState("");
  const editorRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    requestJson("/api/projects", { signal: controller.signal })
      .then(setProjects)
      .catch((error) => { if (!controller.signal.aborted) setError(error.message); });
    return () => controller.abort();
  }, []);

  async function chooseProject(next) {
    setSwitching(true);
    setError("");
    try {
      await editorRef.current?.flush();
      setProject(next);
    } catch (error) {
      setError(error.message);
    } finally {
      setSwitching(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>video-to-guide</h1>
        <select aria-label="Project" value={project} disabled={locked || switching}
          onChange={(e) => chooseProject(e.target.value)}>
          <option value="">choose a project…</option>
          {projects.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        {error && <span role="alert" className="notice">{error}</span>}
      </header>
      {project && <ProjectEditor key={project} project={project} editorRef={editorRef}
        disabled={switching} onLockChange={setLocked} />}
    </div>
  );
}

function ProjectEditor({ project, editorRef, disabled, onLockChange }) {
  const base = `/api/projects/${encodeURIComponent(project)}`;
  const [manifest, setManifest] = useState(null);
  const [guide, setGuide] = useState(null);
  const guideRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [exportUrl, setExportUrl] = useState("");
  const [annotating, setAnnotating] = useState(null);
  const [notice, setNotice] = useState("");
  const [loadError, setLoadError] = useState("");
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [saveStatus, setSaveStatus] = useState({ pending: 0, error: null });
  const [saves] = useState(() => createSaveQueue(
    (next) => requestJson(`${base}/guide`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(next),
    }),
    setSaveStatus
  ));

  useEffect(() => {
    const controller = new AbortController();
    const options = { signal: controller.signal };
    setLoadError("");
    requestJson(`${base}/guide`, options).then((next) => {
      if (controller.signal.aborted) return;
      guideRef.current = next;
      setGuide(next);
    }).catch((error) => { if (!controller.signal.aborted) setLoadError(error.message); });
    fetch(`${base}/frames`, options).then(async (response) => {
      if (response.status === 404) return null;
      if (!response.ok) throw new Error(`Cannot load frames (${response.status})`);
      return response.json();
    }).then((next) => {
      if (!controller.signal.aborted) setManifest(next);
    }).catch((error) => { if (!controller.signal.aborted) setNotice(error.message); });
    return () => controller.abort();
  }, [base, loadAttempt]);

  useEffect(() => {
    onLockChange(busy || saveStatus.pending > 0 || Boolean(saveStatus.error));
    return () => onLockChange(false);
  }, [busy, saveStatus, onLockChange]);

  useImperativeHandle(editorRef, () => ({
    async flush() {
      if (busyRef.current) throw new Error("Wait for the current operation to finish.");
      await saves.flush();
    },
  }), [saves]);

  function persist(next) {
    const updated = typeof next === "function" ? next(guideRef.current) : next;
    guideRef.current = updated;
    setGuide(updated);
    setExportUrl("");
    return saves.enqueue(updated);
  }

  function saveGuide(next) {
    // Queue status retains the error and offers a retry without discarding edits.
    persist(next).catch(() => {});
  }

  async function runOperation(action) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setNotice("");
    try {
      await saves.flush();
      await action();
    } catch (error) {
      setNotice(error.message);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  function extractFrames() {
    return runOperation(async () => {
      setManifest(await requestJson(`${base}/extract`, { method: "POST" }));
    });
  }

  function capture(timestamp) {
    return runOperation(async () => {
      const captured = await requestJson(`${base}/capture`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timestamp }),
      });
      await persist((current) => {
        const sections = structuredClone(current.sections);
        if (!sections.length) sections.push({ id: crypto.randomUUID(), title: "Steps", steps: [] });
        sections[0].steps.push({
          id: crypto.randomUUID(), timestamp: captured.timestamp, frame: captured.file,
          instruction: "", suggestions: [], annotations: [],
        });
        return { ...current, sections };
      });
    });
  }

  function suggest() {
    return runOperation(async () => {
      const data = await requestJson(`${base}/suggestions`, { method: "POST" });
      guideRef.current = data.guide;
      setGuide(data.guide);
      setNotice(data.segments === 0 ? "No narration found in the video audio."
        : `${data.segments} transcript segments matched to steps`);
    });
  }

  function doExport() {
    setExportUrl("");
    return runOperation(async () => {
      // Also persist a new, empty guide before its first export.
      await persist(guideRef.current);
      await requestJson(`${base}/export`, { method: "POST" });
      setExportUrl(`/exports/${encodeURIComponent(project)}/guide.html`);
    });
  }

  let selected = null;
  guide?.sections.forEach((section, sec) => {
    const idx = section.steps.findIndex((step) => step.id === annotating);
    if (idx !== -1) selected = { sec, idx };
  });

  return (
    <>
      <div className="editor-status" aria-live="polite">
        {saveStatus.pending > 0 && <span>Saving…</span>}
        {saveStatus.error && <>
          <span role="alert">Not saved: {saveStatus.error}</span>
          <button disabled={saveStatus.pending > 0 || busy} onClick={() => saveGuide(guideRef.current)}>Retry save</button>
        </>}
        {notice && <span className="notice">{notice}</span>}
        {loadError && <>
          <span role="alert">Cannot load guide: {loadError}</span>
          <button onClick={() => setLoadAttempt((n) => n + 1)}>Retry loading</button>
        </>}
        {!guide && !loadError && <span>Loading guide…</span>}
      </div>
      <fieldset className="editor" disabled={disabled || busy || !guide}>
        <div className="editor-bar">
          <button onClick={suggest}>{busy ? "Working…" : "✦ Suggest from audio"}</button>
          <button onClick={doExport}>Export HTML + PDF</button>
          {exportUrl && <a href={exportUrl} target="_blank" rel="noreferrer">view guide</a>}
        </div>
        {guide && <main inert={busy || disabled}>
          {selected ? <Annotator key={annotating} project={project} guide={guide}
            secIndex={selected.sec} stepIndex={selected.idx} onSave={saveGuide}
            onBack={() => setAnnotating(null)} />
            : <VideoPicker project={project} manifest={manifest} busy={busy}
              onExtract={extractFrames} onCapture={capture} />}
          <SectionOrganizer project={project} guide={guide} onSave={saveGuide}
            onAnnotate={setAnnotating} />
        </main>}
      </fieldset>
    </>
  );
}
