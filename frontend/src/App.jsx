import React, { useEffect, useState } from "react";
import VideoPicker from "./VideoPicker.jsx";
import StepList from "./StepList.jsx";
import Annotator from "./Annotator.jsx";

export default function App() {
  const [projects, setProjects] = useState([]);
  const [project, setProject] = useState("");
  const [manifest, setManifest] = useState(null);
  const [guide, setGuide] = useState(null);
  const [busy, setBusy] = useState(false);
  const [exportUrl, setExportUrl] = useState("");
  const [annotating, setAnnotating] = useState(null);

  useEffect(() => {
    fetch("/api/projects")
      .then((r) => r.json())
      .then(setProjects)
      .catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    if (!project) return;
    setManifest(null);
    setExportUrl("");
    setAnnotating(null);
    fetch(`/api/projects/${project}/guide`)
      .then((r) => r.json())
      .then(setGuide);
    fetch(`/api/projects/${project}/frames`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setManifest);
  }, [project]);

  async function saveGuide(next) {
    setGuide(next);
    await fetch(`/api/projects/${project}/guide`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(next),
    });
  }

  async function extractFrames() {
    setBusy(true);
    try {
      await fetch(`/api/projects/${project}/extract`, { method: "POST" });
      setManifest(
        await fetch(`/api/projects/${project}/frames`).then((r) => r.json())
      );
    } finally {
      setBusy(false);
    }
  }

  async function capture(timestamp) {
    const r = await fetch(`/api/projects/${project}/capture`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ timestamp }),
    });
    if (!r.ok) return;
    const captured = await r.json();
    const sections = JSON.parse(JSON.stringify(guide.sections || []));
    if (!sections.length) {
      sections.push({ id: "sec-1", title: "Steps", steps: [] });
    }
    const n = Math.max(
      0,
      ...sections.flatMap((s) => s.steps.map((st) => Number(st.id.replace("step-", "")) || 0))
    ) + 1;
    sections[0].steps.push({
      id: `step-${n}`,
      timestamp: captured.timestamp,
      frame: captured.file,
      instruction: "",
      annotations: [],
    });
    await saveGuide({ ...guide, sections });
  }

  async function doExport() {
    setBusy(true);
    try {
      await fetch(`/api/projects/${project}/export`, { method: "POST" });
      setExportUrl(`/exports/${project}/guide.html`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>video-to-guide</h1>
        <select value={project} onChange={(e) => setProject(e.target.value)}>
          <option value="">choose a project…</option>
          {projects.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        {project && (
          <button onClick={doExport} disabled={busy}>Export HTML + PDF</button>
        )}
        {exportUrl && (
          <a href={exportUrl} target="_blank" rel="noreferrer">view guide</a>
        )}
      </header>

      {project && guide && (
        <main>
          {annotating != null && guide.sections[0]?.steps[annotating] ? (
            <Annotator
              project={project}
              guide={guide}
              stepIndex={annotating}
              onSave={saveGuide}
              onBack={() => setAnnotating(null)}
            />
          ) : (
            <VideoPicker
              project={project}
              manifest={manifest}
              busy={busy}
              onExtract={extractFrames}
              onCapture={capture}
            />
          )}
          <StepList
            project={project}
            guide={guide}
            onSave={saveGuide}
            onAnnotate={setAnnotating}
          />
        </main>
      )}
    </div>
  );
}
