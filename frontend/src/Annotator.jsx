import React, { useEffect, useRef, useState } from "react";

const COLORS = ["#e53e3e", "#2b6cb0", "#2f855a", "#d69e2e", "#1a202c"];
const TOOLS = [
  { id: "box", label: "Box" },
  { id: "arrow", label: "Arrow" },
  { id: "text", label: "Text" },
  { id: "redact", label: "Redact" },
];

export default function Annotator({ project, guide, secIndex, stepIndex, onSave, onBack }) {
  const step = guide.sections[secIndex]?.steps[stepIndex];
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const dragStart = useRef(null);
  const [tool, setTool] = useState("box");
  const [color, setColor] = useState(COLORS[0]);
  const [mode, setMode] = useState("solid");
  const [draft, setDraft] = useState(null);
  const [textAt, setTextAt] = useState(null);
  const [textValue, setTextValue] = useState("");
  const [, setLoaded] = useState(false);

  const frameFile = step ? step.frame.split("/").pop() : "";

  useEffect(() => {
    if (!step) return;
    const img = new Image();
    img.onload = () => {
      imgRef.current = img;
      setLoaded((v) => !v);
    };
    img.src = `/media/${project}/frames/${frameFile}`;
  }, [project, frameFile]);

  function draw() {
    const img = imgRef.current;
    const canvas = canvasRef.current;
    if (!img || !canvas || !step) return;
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0);
    for (const a of step.annotations) drawAnnotation(ctx, a, img);
    if (draft) drawAnnotation(ctx, draftToAnnotation(draft), img);
  }

  useEffect(draw);

  function toOriginal(e) {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    return {
      x: Math.round(((e.clientX - rect.left) * canvas.width) / rect.width),
      y: Math.round(((e.clientY - rect.top) * canvas.height) / rect.height),
    };
  }

  function draftToAnnotation(d) {
    if (tool === "arrow") {
      return { type: "arrow", x: d.x0, y: d.y0, w: d.x1 - d.x0, h: d.y1 - d.y0, color };
    }
    const x = Math.min(d.x0, d.x1);
    const y = Math.min(d.y0, d.y1);
    const w = Math.abs(d.x1 - d.x0);
    const h = Math.abs(d.y1 - d.y0);
    if (tool === "redact") return { type: "redact", x, y, w, h, mode };
    return { type: "box", x, y, w, h, color };
  }

  function onMouseDown(e) {
    if (tool === "text") {
      const p = toOriginal(e);
      setTextAt(p);
      setTextValue("");
      return;
    }
    const p = toOriginal(e);
    dragStart.current = p;
    setDraft({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
  }

  function onMouseMove(e) {
    if (!dragStart.current) return;
    const p = toOriginal(e);
    setDraft((d) => ({ ...d, x1: p.x, y1: p.y }));
  }

  function onMouseUp() {
    if (!draft) return;
    dragStart.current = null;
    const dx = Math.abs(draft.x1 - draft.x0);
    const dy = Math.abs(draft.y1 - draft.y0);
    if (dx > 8 || dy > 8) {
      addAnnotation(draftToAnnotation(draft));
    }
    setDraft(null);
  }

  function commitText() {
    const value = textValue.trim();
    if (value && textAt) {
      const img = imgRef.current;
      addAnnotation({
        type: "text",
        x: textAt.x,
        y: textAt.y,
        text: value,
        color,
        size: Math.max(16, Math.round(img.naturalHeight / 30)),
      });
    }
    setTextAt(null);
    setTextValue("");
  }

  function updateAnnotations(next) {
    const sections = JSON.parse(JSON.stringify(guide.sections));
    sections[secIndex].steps[stepIndex].annotations = next;
    onSave({ ...guide, sections });
  }

  function addAnnotation(a) {
    updateAnnotations([...(step.annotations ?? []), a]);
  }

  function removeAnnotation(i) {
    updateAnnotations(step.annotations.filter((_, j) => j !== i));
  }

  if (!step) return null;

  const drawTools = ["box", "arrow", "redact"];

  return (
    <section className="picker annotator">
      <div className="annotator-bar">
        <button onClick={onBack}>← Video</button>
        <span className="step-badge">{step.id}</span>
        {TOOLS.map((t) => (
          <button
            key={t.id}
            className={tool === t.id ? "active" : ""}
            onClick={() => setTool(t.id)}
          >
            {t.label}
          </button>
        ))}
        {tool === "redact" && (
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="solid">solid</option>
            <option value="pixelate">pixelate</option>
            <option value="blur">blur</option>
          </select>
        )}
        {tool !== "redact" && (
          <span className="palette">
            {COLORS.map((c) => (
              <button
                key={c}
                className={"swatch" + (color === c ? " active" : "")}
                style={{ background: c }}
                onClick={() => setColor(c)}
                title={c}
              />
            ))}
          </span>
        )}
      </div>

      <div className="canvas-wrap">
        <canvas
          ref={canvasRef}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
        />
        {textAt && (
          <input
            className="text-input"
            autoFocus
            value={textValue}
            style={{
              left: `${(textAt.x / canvasRef.current.width) * 100}%`,
              top: `${(textAt.y / canvasRef.current.height) * 100}%`,
              color,
            }}
            onChange={(e) => setTextValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitText();
              if (e.key === "Escape") {
                setTextValue("");
                setTextAt(null);
              }
            }}
            onBlur={commitText}
            placeholder="type, Enter to place"
          />
        )}
      </div>

      <div className="ann-list">
        {step.annotations.length === 0 && (
          <p className="hint">Drag on the image to add annotations.</p>
        )}
        {step.annotations.map((a, i) => (
          <span key={i} className="chip" style={{ borderLeftColor: a.color || "#718096" }}>
            {a.type}
            {a.text ? `: ${a.text.slice(0, 18)}` : ""}
            <button onClick={() => removeAnnotation(i)}>✕</button>
          </span>
        ))}
      </div>
      <p className="hint">
        Redactions are baked into pixels on export. Solid is the only guaranteed
        redaction; blur and pixelate just de-emphasize.
      </p>
    </section>
  );
}

function drawAnnotation(ctx, a, img) {
  const lw = Math.max(3, Math.round(img.naturalHeight / 250));
  if (a.type === "box") {
    ctx.strokeStyle = a.color || "#e53e3e";
    ctx.lineWidth = lw;
    ctx.strokeRect(a.x, a.y, a.w || 0, a.h || 0);
  } else if (a.type === "arrow") {
    drawArrow(ctx, a, lw);
  } else if (a.type === "text") {
    const size = a.size || 24;
    ctx.font = `${size}px -apple-system, "Segoe UI", Roboto, sans-serif`;
    ctx.textBaseline = "top";
    const w = ctx.measureText(a.text).width;
    ctx.fillStyle = "rgba(255,255,255,0.92)";
    ctx.fillRect(a.x - 4, a.y - 3, w + 10, size + 8);
    ctx.strokeStyle = "#cbd5e0";
    ctx.lineWidth = 1;
    ctx.strokeRect(a.x - 4, a.y - 3, w + 10, size + 8);
    ctx.fillStyle = a.color || "#1a202c";
    ctx.fillText(a.text, a.x, a.y);
  } else if (a.type === "redact") {
    drawRedact(ctx, a, img);
  }
}

function drawArrow(ctx, a, lw) {
  const color = a.color || "#e53e3e";
  const ex = a.x + (a.w || 0);
  const ey = a.y + (a.h || 0);
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = lw;
  ctx.beginPath();
  ctx.moveTo(a.x, a.y);
  ctx.lineTo(ex, ey);
  ctx.stroke();
  const head = Math.max(lw * 4, 14);
  const angle = Math.atan2(ey - a.y, ex - a.x);
  const spread = (155 * Math.PI) / 180;
  ctx.beginPath();
  ctx.moveTo(ex, ey);
  ctx.lineTo(ex + head * Math.cos(angle + spread), ey + head * Math.sin(angle + spread));
  ctx.lineTo(ex + head * Math.cos(angle - spread), ey + head * Math.sin(angle - spread));
  ctx.closePath();
  ctx.fill();
}

function drawRedact(ctx, a, img) {
  const x = a.x, y = a.y, w = a.w || 0, h = a.h || 0;
  if (w <= 0 || h <= 0) return;
  if (a.mode === "solid") {
    ctx.fillStyle = "#111111";
    ctx.fillRect(x, y, w, h);
    return;
  }
  if (a.mode === "pixelate") {
    const block = Math.max(12, Math.floor(Math.min(w, h) / 10));
    const tw = Math.max(1, Math.floor(w / block));
    const th = Math.max(1, Math.floor(h / block));
    const t = document.createElement("canvas");
    t.width = tw;
    t.height = th;
    t.getContext("2d").drawImage(img, x, y, w, h, 0, 0, tw, th);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(t, 0, 0, tw, th, x, y, w, h);
    ctx.imageSmoothingEnabled = true;
    return;
  }
  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y, w, h);
  ctx.clip();
  ctx.filter = "blur(14px)";
  ctx.drawImage(img, 0, 0);
  ctx.filter = "none";
  ctx.restore();
}
