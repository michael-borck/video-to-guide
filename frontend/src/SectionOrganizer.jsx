import React, { useRef } from "react";
import { mediaUrl } from "./api.js";

export default function SectionOrganizer({ project, guide, onSave, onAnnotate }) {
  const drag = useRef(null);
  const sections = guide.sections ?? [];

  function update(nextSections) {
    onSave({ ...guide, sections: nextSections });
  }

  function moveStep(from, toSec, toIdx) {
    const next = JSON.parse(JSON.stringify(sections));
    const [step] = next[from.sec].steps.splice(from.idx, 1);
    let at = toIdx;
    if (from.sec === toSec && from.idx < toIdx) at -= 1;
    next[toSec].steps.splice(at, 0, step);
    update(next);
  }

  function moveSection(sec, delta) {
    const next = JSON.parse(JSON.stringify(sections));
    const target = sec + delta;
    if (target < 0 || target >= next.length) return;
    [next[sec], next[target]] = [next[target], next[sec]];
    update(next);
  }

  function patchStep(sec, idx, patch) {
    const next = JSON.parse(JSON.stringify(sections));
    Object.assign(next[sec].steps[idx], patch);
    update(next);
  }

  function removeStep(sec, idx) {
    const next = JSON.parse(JSON.stringify(sections));
    next[sec].steps.splice(idx, 1);
    update(next);
  }

  function setTitle(sec, title) {
    const next = JSON.parse(JSON.stringify(sections));
    next[sec].title = title;
    update(next);
  }

  function addSection() {
    update([
      ...sections,
      { id: crypto.randomUUID(), title: "New section", steps: [] },
    ]);
  }

  function removeSection(sec) {
    update(sections.filter((_, i) => i !== sec));
  }

  return (
    <aside className="steps">
      <h2>Sections</h2>
      {sections.map((section, sec) => (
        <section
          key={section.id}
          className="guide-section"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (drag.current) moveStep(drag.current, sec, sections[sec].steps.length);
            drag.current = null;
          }}
        >
          <div className="section-head">
            <input
              className="section-title"
              value={section.title}
              onChange={(e) => setTitle(sec, e.target.value)}
            />
            <span className="section-tools">
              <button title="Move up" onClick={() => moveSection(sec, -1)}>↑</button>
              <button title="Move down" onClick={() => moveSection(sec, 1)}>↓</button>
              <button
                title={section.steps.length ? "Remove steps first" : "Remove section"}
                disabled={section.steps.length > 0}
                onClick={() => removeSection(sec)}
              >
                ✕
              </button>
            </span>
          </div>
          {section.steps.length === 0 && <p className="hint">Drop steps here.</p>}
          {section.steps.map((step, idx) => (
            <article
              key={step.id}
              className="step-card"
              draggable
              onDragStart={(e) => {
                drag.current = { sec, idx };
                e.dataTransfer.setData("text/plain", step.id);
                e.dataTransfer.effectAllowed = "move";
              }}
              onDragOver={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
              onDrop={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (drag.current) moveStep(drag.current, sec, idx);
                drag.current = null;
              }}
              onDragEnd={() => {
                drag.current = null;
              }}
              onClick={() => onAnnotate(step.id)}
              title="Click to annotate; drag to reorder"
            >
              <img src={mediaUrl(project, step.frame)} alt="" />
              <div className="step-body">
                <div className="step-meta">
                  <span>{step.id}</span>
                  <span>{step.timestamp.toFixed(1)}s</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeStep(sec, idx);
                    }}
                  >
                    remove
                  </button>
                </div>
                {step.suggestions?.length > 0 && (
                  <button
                    className="suggestion"
                    title="Replace instruction with transcript suggestion"
                    onClick={(e) => {
                      e.stopPropagation();
                      patchStep(sec, idx, { instruction: step.suggestions[0] });
                    }}
                  >
                    ✦ {step.suggestions[0].slice(0, 42)}
                    {step.suggestions[0].length > 42 ? "…" : ""}
                  </button>
                )}
                <textarea
                  placeholder="Instruction text…"
                  value={step.instruction}
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => patchStep(sec, idx, { instruction: e.target.value })}
                />
              </div>
            </article>
          ))}
        </section>
      ))}
      <button onClick={addSection}>＋ Add section</button>
    </aside>
  );
}
