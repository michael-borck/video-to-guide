from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from .model import Step


def extract_audio(video: Path, out_wav: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(video),
            "-vn", "-ar", "16000", "-ac", "1",
            str(out_wav),
        ],
        check=True,
        capture_output=True,
    )


def transcribe(video: Path, model_size: str = "base") -> list[dict]:
    from faster_whisper import WhisperModel

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        extract_audio(video, wav)
        model = WhisperModel(model_size)
        segments, _info = model.transcribe(str(wav))
        return [
            {"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip()}
            for s in segments
            if s.text.strip()
        ]


def transcribe_cached(video: Path, model_size: str = "base") -> list[dict]:
    out = video.parent / "transcript.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    segments = transcribe(video, model_size)
    out.write_text(json.dumps(segments, indent=2), encoding="utf-8")
    return segments


def suggestions_for_steps(segments: list[dict], steps: list[Step]) -> list[str]:
    order = sorted(range(len(steps)), key=lambda i: steps[i].timestamp)
    bounds = [steps[i].timestamp for i in order]
    texts = [[] for _ in steps]
    for seg in segments:
        best, best_overlap = None, 0.0
        for pos, i in enumerate(order):
            start = bounds[pos]
            end = bounds[pos + 1] if pos + 1 < len(bounds) else float("inf")
            overlap = min(seg["end"], end) - max(seg["start"], start)
            if overlap > best_overlap:
                best, best_overlap = i, overlap
        if best is not None:
            texts[best].append(seg["text"])
    return [" ".join(t).strip() for t in texts]
