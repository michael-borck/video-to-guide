from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


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
    path.write_text(guide.model_dump_json(indent=2), encoding="utf-8")
