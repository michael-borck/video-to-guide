import React, { useRef } from "react";

export default function VideoPicker({ project, manifest, busy, onExtract, onCapture }) {
  const videoRef = useRef(null);

  function seek(t) {
    if (videoRef.current) {
      videoRef.current.currentTime = t;
    }
  }

  return (
    <section className="picker">
      <video
        ref={videoRef}
        src={`/media/${project}/video.mp4`}
        controls
        onClick={(e) => e.stopPropagation()}
      />
      <div className="picker-bar">
        <button
          className="primary"
          disabled={!videoRef.current}
          onClick={() => onCapture(videoRef.current.currentTime)}
        >
          Capture this frame
        </button>
        {!manifest && (
          <button onClick={onExtract} disabled={busy}>
            {busy ? "Extracting…" : "Extract candidate frames"}
          </button>
        )}
      </div>
      {manifest && (
        <div className="filmstrip">
          {manifest.frames.map((f) => (
            <figure key={f.file} onClick={() => seek(f.timestamp)} title={f.file}>
              <img src={`/media/${project}/frames/${f.file}`} alt={f.file} />
              <figcaption>{f.timestamp.toFixed(1)}s</figcaption>
            </figure>
          ))}
        </div>
      )}
    </section>
  );
}
