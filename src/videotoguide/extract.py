from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import imagehash
from PIL import Image
from scenedetect import ContentDetector, FrameTimecode, detect


@dataclass
class FrameCandidate:
    file: str
    timestamp: float
    sharpness: float


@dataclass
class ExtractionResult:
    video: str
    width: int
    height: int
    fps: float
    duration: float
    frames: list[FrameCandidate]


def _sharpness(img) -> float:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _best_in_scene(
    cap: cv2.VideoCapture, start: int, end: int, samples: int
) -> tuple[int, object, float] | None:
    span = max(end - start, 1)
    best: tuple[int, object, float] | None = None
    for i in range(samples):
        frame_no = start + int(span * (i + 0.5) / samples)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ok, img = cap.read()
        if not ok:
            continue
        score = _sharpness(img)
        if best is None or score > best[2]:
            best = (frame_no, img, score)
    return best


def _dedupe(
    candidates: list[FrameCandidate], out_dir: Path, threshold: int
) -> list[FrameCandidate]:
    kept: list[FrameCandidate] = []
    hashes: list[imagehash.ImageHash] = []
    for cand in candidates:
        h = imagehash.phash(Image.open(out_dir / cand.file))
        if any(h - existing <= threshold for existing in hashes):
            (out_dir / cand.file).unlink()
            continue
        hashes.append(h)
        kept.append(cand)
    return kept


def extract_frames(
    video: Path,
    out_dir: Path | None = None,
    scene_threshold: float = 27.0,
    min_scene_len_s: float = 1.0,
    samples_per_scene: int = 8,
    dedup_threshold: int = 8,
    max_frames: int = 40,
) -> ExtractionResult:
    video = Path(video)
    if max_frames < 1 or samples_per_scene < 1:
        raise ValueError("max_frames and samples_per_scene must be positive")
    out_dir = Path(out_dir) if out_dir else video.parent / "frames"
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps

    picked: list[tuple[float, int, object, float]] = []
    try:
        scenes = detect(
            str(video),
            ContentDetector(
                threshold=scene_threshold,
                min_scene_len=max(1, round(min_scene_len_s * fps)),
            ),
        )
        if not scenes:
            end = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            scenes = [(FrameTimecode(0, fps=fps), FrameTimecode(end, fps=fps))]
        if len(scenes) > max_frames:
            # Include both ends and distribute the remaining slots across the video.
            indices = (
                [round(i * (len(scenes) - 1) / (max_frames - 1)) for i in range(max_frames)]
                if max_frames > 1 else [len(scenes) // 2]
            )
            scenes = [scenes[i] for i in indices]
        for start_fc, end_fc in scenes:
            result = _best_in_scene(cap, start_fc.frame_num, end_fc.frame_num, samples_per_scene)
            if result is None:
                continue
            frame_no, img, score = result
            picked.append((frame_no / fps, frame_no, img, score))
    finally:
        cap.release()

    picked.sort(key=lambda item: item[0])

    candidates: list[FrameCandidate] = []
    for i, (timestamp, _frame_no, img, score) in enumerate(picked, start=1):
        name = f"frame_{i:04d}.png"
        cv2.imwrite(str(out_dir / name), img)
        candidates.append(FrameCandidate(file=name, timestamp=round(timestamp, 3), sharpness=round(score, 1)))

    candidates = _dedupe(candidates, out_dir, dedup_threshold)

    result = ExtractionResult(
        video=video.name,
        width=width,
        height=height,
        fps=round(fps, 3),
        duration=round(duration, 3),
        frames=candidates,
    )
    (out_dir / "manifest.json").write_text(
        json.dumps(asdict(result), indent=2), encoding="utf-8"
    )
    return result
