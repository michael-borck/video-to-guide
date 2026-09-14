import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient
from PIL import Image
from scenedetect import FrameTimecode

from backend import main as api
from videotoguide.export import export_guide, export_html
from videotoguide.extract import extract_frames
from videotoguide.model import Annotation, Guide, Section, Step, load_guide, save_guide


class RegressionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="vtg-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "projects" / "demo"
        self.frames = self.project / "frames"
        self.frames.mkdir(parents=True)
        Image.new("RGB", (32, 32), "white").save(self.frames / "source.png")
        self.out = self.root / "exports" / "demo"
        self.enterContext(patch.object(api, "PROJECTS", self.project.parent))
        self.enterContext(patch.object(api, "EXPORTS", self.out.parent))
        self.client = self.enterContext(TestClient(api.app, raise_server_exceptions=False))

    def guide(self, steps=None):
        if steps is None:
            steps = [Step(id="one", timestamp=0, frame="frames/source.png")]
        return Guide(title="test", sections=[Section(id="s", title="section", steps=steps)])

    def video(self):
        path = self.project / "video.mp4"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 64))
        self.assertTrue(writer.isOpened())
        for _ in range(60):
            writer.write(np.full((64, 64, 3), 128, dtype=np.uint8))
        writer.release()
        return path

    def test_manifest_is_a_json_object(self):
        manifest = {"frames": [{"file": "source.png", "timestamp": 0}]}
        (self.frames / "manifest.json").write_text(json.dumps(manifest))
        response = self.client.get("/api/projects/demo/frames")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), manifest)

    def test_repeated_source_has_independent_redaction(self):
        redacted = Step(id="one", timestamp=0, frame="frames/source.png", annotations=[
            Annotation(type="redact", x=0, y=0, w=31, h=31, mode="solid")])
        plain = Step(id="two", timestamp=1, frame="frames/source.png")
        html = export_html(self.guide([redacted, plain]), self.project, self.out).read_text()
        self.assertIn('src="frames/step_0001.png"', html)
        self.assertIn('src="frames/step_0002.png"', html)
        with Image.open(self.out / "frames" / "step_0001.png") as image:
            self.assertEqual(image.getpixel((5, 5)), (17, 17, 17))
        with Image.open(self.out / "frames" / "step_0002.png") as image:
            self.assertEqual(image.getpixel((5, 5)), (255, 255, 255))

    def test_reexport_removes_old_assets(self):
        export_html(self.guide(), self.project, self.out)
        export_html(self.guide([]), self.project, self.out)
        self.assertEqual(list((self.out / "frames").iterdir()), [])

    def test_failed_render_preserves_previous_export(self):
        previous = export_html(self.guide(), self.project, self.out).read_bytes()
        missing = Step(id="missing", timestamp=0, frame="frames/missing.png")
        with self.assertRaises(FileNotFoundError):
            export_html(self.guide([missing]), self.project, self.out)
        self.assertEqual((self.out / "guide.html").read_bytes(), previous)
        self.assertTrue((self.out / "frames" / "step_0001.png").exists())

    def test_export_cannot_replace_source_project(self):
        for destination in (self.project, self.project.parent, self.frames):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                export_html(self.guide(), self.project, destination)
        self.assertTrue((self.frames / "source.png").exists())

    def test_failed_pdf_preserves_entire_previous_export(self):
        export_html(self.guide(), self.project, self.out)
        (self.out / "guide.pdf").write_bytes(b"previous PDF")
        previous = (self.out / "guide.html").read_bytes()
        with patch("videotoguide.export.export_pdf", side_effect=RuntimeError("Chrome unavailable")):
            with self.assertRaisesRegex(RuntimeError, "Chrome unavailable"):
                export_guide(self.guide([]), self.project, self.out)
        self.assertEqual((self.out / "guide.pdf").read_bytes(), b"previous PDF")
        self.assertEqual((self.out / "guide.html").read_bytes(), previous)
        self.assertEqual(list(self.out.parent.iterdir()), [self.out])

    def test_successful_bundle_replaces_old_images_and_pdf(self):
        export_html(self.guide(), self.project, self.out)
        def fake_pdf(html_path, pdf_path):
            self.assertTrue(html_path.exists())
            pdf_path.write_bytes(b"new PDF")
            return pdf_path
        with patch("videotoguide.export.export_pdf", side_effect=fake_pdf):
            html, pdf = export_guide(self.guide([]), self.project, self.out)
        self.assertTrue(html.exists())
        self.assertEqual(pdf.read_bytes(), b"new PDF")
        self.assertEqual(list((self.out / "frames").iterdir()), [])

    def test_api_rejects_outside_frame_paths(self):
        for frame in ("../../private.png", "frames/../../private.png", "/tmp/private.png", r"frames\..\private.png"):
            with self.subTest(frame=frame):
                guide = self.guide().model_dump()
                guide["sections"][0]["steps"][0]["frame"] = frame
                response = self.client.put("/api/projects/demo/guide", json=guide)
                self.assertEqual(response.status_code, 422)

    def test_symlink_cannot_escape_frames(self):
        outside = self.root / "private.png"
        Image.new("RGB", (32, 32), "red").save(outside)
        (self.frames / "linked.png").symlink_to(outside)
        guide = self.guide([Step(id="link", timestamp=0, frame="frames/linked.png")])
        response = self.client.put("/api/projects/demo/guide", json=guide.model_dump())
        self.assertEqual(response.status_code, 400)
        with self.assertRaises(ValueError):
            export_html(guide, self.project, self.out)

    def test_failed_atomic_save_preserves_guide(self):
        path = self.project / "guide.json"
        save_guide(self.guide(), path)
        previous = path.read_bytes()
        with patch("videotoguide.model.os.replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                save_guide(Guide(title="new"), path)
        self.assertEqual(path.read_bytes(), previous)
        self.assertEqual(set(self.project.iterdir()), {path, self.frames})
        save_guide(Guide(title="retry"), path)
        self.assertEqual(load_guide(path).title, "retry")

    def test_missing_transcription_extra_is_actionable(self):
        (self.project / "video.mp4").touch()
        with patch.dict(sys.modules, {"faster_whisper": None}):
            response = self.client.post("/api/projects/demo/suggestions")
        self.assertEqual(response.status_code, 400)
        self.assertIn("uv sync --extra transcribe", response.json()["detail"])

    def test_static_video_has_a_candidate(self):
        result = extract_frames(self.video(), out_dir=self.root / "static-frames")
        self.assertEqual(result.duration, 2)
        self.assertEqual(len(result.frames), 1)

    def test_capped_candidates_include_beginning_and_end(self):
        video = self.video()
        scenes = [(FrameTimecode(i, fps=30.0), FrameTimecode(i + 1, fps=30.0)) for i in range(6)]
        with patch("videotoguide.extract.detect", return_value=scenes):
            result = extract_frames(video, out_dir=self.root / "limited", max_frames=2, dedup_threshold=-1)
        self.assertEqual([frame.timestamp for frame in result.frames], [0, 0.167])

    def test_invalid_extraction_and_capture_limits_are_rejected(self):
        self.assertEqual(self.client.post("/api/projects/demo/extract?max_frames=0").status_code, 422)
        self.assertEqual(self.client.post("/api/projects/demo/capture", json={"timestamp": -1}).status_code, 422)

    def test_export_failure_is_reported(self):
        save_guide(self.guide(), self.project / "guide.json")
        with patch("videotoguide.export.export_pdf", side_effect=RuntimeError("Chrome unavailable")):
            response = self.client.post("/api/projects/demo/export")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Chrome unavailable", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
