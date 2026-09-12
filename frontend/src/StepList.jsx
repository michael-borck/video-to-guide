import React from "react";

export default function StepList({ project, guide, onSave }) {
  const steps = guide.sections[0]?.steps ?? [];

  function update(stepIndex, patch) {
    const sections = JSON.parse(JSON.stringify(guide.sections));
    Object.assign(sections[0].steps[stepIndex], patch);
    onSave({ ...guide, sections });
  }

  function remove(stepIndex) {
    const sections = JSON.parse(JSON.stringify(guide.sections));
    sections[0].steps.splice(stepIndex, 1);
    onSave({ ...guide, sections });
  }

  return (
    <aside className="steps">
      <h2>Steps ({steps.length})</h2>
      {steps.length === 0 && <p className="hint">Capture frames to build the guide.</p>}
      {steps.map((step, i) => (
        <article key={step.id} className="step-card">
          <img src={`/media/${project}/frames/${fileName(step.frame)}`} alt="" />
          <div className="step-body">
            <div className="step-meta">
              <span>{step.id}</span>
              <span>{step.timestamp.toFixed(1)}s</span>
              <button onClick={() => remove(i)}>remove</button>
            </div>
            <textarea
              placeholder="Instruction text…"
              defaultValue={step.instruction}
              onBlur={(e) =>
                e.target.value !== step.instruction &&
                update(i, { instruction: e.target.value })
              }
            />
          </div>
        </article>
      ))}
    </aside>
  );
}

function fileName(frame) {
  return frame.split("/").pop();
}
