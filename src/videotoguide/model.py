from __future__ import annotations

import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Annotation(BaseModel):
    type: Literal["box", "text", "arrow", "redact"]
    x: int
    y: int
    w: int | None = None
    h: int | None = None
    text: str | None = None
    color: str | None = None
    size: int | None = None
    mode: Literal["solid", "pixelate", "blur"] | None = None


class Step(BaseModel):
    id: str
    timestamp: float
    frame: str
    instruction: str = ""
    suggestions: list[str] = Field(default_factory=list)
    annotations: list[Annotation] = Field(default_factory=list)

    @field_validator("frame")
    @classmethod
    def validate_frame(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            "\\" in value
            or "\x00" in value
            or path.is_absolute()
            or ".." in path.parts
            or len(path.parts) < 2
            or path.parts[0] != "frames"
        ):
            raise ValueError("frame must be a relative path inside frames/")
        return value


class Section(BaseModel):
    id: str
    title: str
    steps: list[Step] = Field(default_factory=list)


class Guide(BaseModel):
    title: str
    sections: list[Section] = Field(default_factory=list)


def load_guide(path: Path) -> Guide:
    return Guide.model_validate_json(path.read_text(encoding="utf-8"))


def save_guide(guide: Guide, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as file:
            temporary = Path(file.name)
            file.write(guide.model_dump_json(indent=2))
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def resolve_frame(project_dir: Path, frame: str) -> Path:
    """Check resolved paths as well as the model, so symlinks cannot escape."""
    project = project_dir.resolve()
    frames = (project / "frames").resolve()
    source = (project / frame).resolve()
    if not frames.is_relative_to(project) or not source.is_relative_to(frames):
        raise ValueError("frame must stay inside the project's frames directory")
    return source
