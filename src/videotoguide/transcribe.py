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
    """Transcribe a video's narration via speech-analyser (the family's audio member).

    speech-analyser wraps faster-whisper with word-level timestamps and language
    detection, so segment dicts carry a ``words`` list ({word, start, end,
    probability}) that step suggestions can snap to. Audio is extracted to a
    temp WAV first because speech-analyser accepts audio formats only.
    """
    from speech_analyser import SpeechAnalyser

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        extract_audio(video, wav)
        result = SpeechAnalyser(model_size=model_size).analyse(wav)

    segments: list[dict] = []
    for seg in result.get("segments", []):
        if not seg.get("text"):
            continue
        item = {"start": seg["start"], "end": seg["end"], "text": seg["text"]}
        if seg.get("words"):
            item["words"] = seg["words"]
        segments.append(item)
    return segments


def transcribe_cached(video: Path, model_size: str = "base") -> list[dict]:
    out = video.parent / "transcript.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    segments = transcribe(video, model_size)
    out.write_text(json.dumps(segments, indent=2), encoding="utf-8")
    return segments


def suggestions_for_steps(segments: list[dict], steps: list[Step]) -> list[str]:
    """Draft instruction text for each step from the narration overlapping it.

    Without word timings, whole segments are assigned by maximum time overlap
    with the step's window. With them, only words whose midpoint falls inside
    the window contribute — a segment straddling two steps no longer
    double-counts into both.
    """
    order = sorted(range(len(steps)), key=lambda i: steps[i].timestamp)
    bounds = [steps[i].timestamp for i in order]
    texts: list[list[str]] = [[] for _ in steps]

    if segments and all(seg.get("words") for seg in segments):
        for seg in segments:
            for w in seg["words"]:
                mid = (w["start"] + w["end"]) / 2
                pos = _window_for(bounds, mid)
                if pos is not None:
                    texts[order[pos]].append(w["word"])
    else:
        for seg in segments:
            pos = _best_overlap_window(bounds, seg["start"], seg["end"])
            if pos is not None:
                texts[order[pos]].append(seg["text"])
    return [" ".join(t).strip() for t in texts]


def _window_for(bounds: list[float], t: float) -> int | None:
    """Index of the step window containing time ``t`` (None before the first step)."""
    for pos in range(len(bounds)):
        end = bounds[pos + 1] if pos + 1 < len(bounds) else float("inf")
        if bounds[pos] <= t < end:
            return pos
    return None


def _best_overlap_window(bounds: list[float], start: float, end: float) -> int | None:
    """Index of the step window with maximum time overlap of [start, end)."""
    best, best_overlap = None, 0.0
    for pos in range(len(bounds)):
        w_end = bounds[pos + 1] if pos + 1 < len(bounds) else float("inf")
        overlap = min(end, w_end) - max(start, bounds[pos])
        if overlap > best_overlap:
            best, best_overlap = pos, overlap
    return best
