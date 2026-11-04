"""Board JSON contract, version 1.

A board is one topic taught in four sections: Picture, Notes, Practice and
Progress. The model is deliberately plain data so another client (a phone page,
a future Vex integration) can read it without importing DeepTutor.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = 1

BOARD_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
QuestionType = Literal["single_choice", "multi_choice", "true_false", "fill_blank", "short_answer"]
CHOICE_TYPES = ("single_choice", "multi_choice")
MasteryStatus = Literal["new", "learning", "mastered"]

MAX_QUESTIONS = 50
MAX_TEXT = 4000


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(*parts: str) -> str:
    """Build a safe board id such as ``civil-construction-planning``."""
    text = "-".join(p for p in parts if p).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text[:80].strip("-")) or "board"


def _clean(value: str) -> str:
    return " ".join(str(value or "").split())


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class Source(_Model):
    kind: Literal["guideline", "past_paper", "other"] = "other"
    name: str = Field(default="", max_length=300)
    ref: str = Field(default="", max_length=500)


class Picture(_Model):
    kind: Literal["svg", "image"] = "svg"
    title: str = Field(default="", max_length=300)
    # Relative path inside the board folder, for example ``assets/picture.svg``.
    asset: str = Field(default="", max_length=200)
    alt: str = Field(default="", max_length=1000)
    caption: str = Field(default="", max_length=1000)

    @field_validator("asset")
    @classmethod
    def _asset_is_relative(cls, value: str) -> str:
        if not value:
            return value
        if (
            value.startswith(("/", "\\"))
            or ".." in value.replace("\\", "/").split("/")
            or ":" in value
        ):
            raise ValueError("asset must be a relative path inside the board folder")
        return value.replace("\\", "/")


class NoteSection(_Model):
    heading: str = Field(max_length=300)
    points: list[str] = Field(default_factory=list, max_length=40)

    @field_validator("points")
    @classmethod
    def _points(cls, value: list[str]) -> list[str]:
        return [_clean(p)[:MAX_TEXT] for p in value if _clean(p)]


class Formula(_Model):
    name: str = Field(max_length=200)
    latex: str = Field(max_length=500)
    explanation: str = Field(default="", max_length=1000)


class KeyTerm(_Model):
    term: str = Field(max_length=200)
    meaning: str = Field(max_length=1000)


class Notes(_Model):
    summary: str = Field(default="", max_length=MAX_TEXT)
    sections: list[NoteSection] = Field(default_factory=list, max_length=30)
    formulas: list[Formula] = Field(default_factory=list, max_length=30)
    key_terms: list[KeyTerm] = Field(default_factory=list, max_length=60)


class Question(_Model):
    id: str = Field(max_length=40)
    type: QuestionType
    question: str = Field(max_length=MAX_TEXT)
    options: dict[str, str] = Field(default_factory=dict)
    marks: int = Field(default=1, ge=0, le=100)
    answer: str = Field(max_length=MAX_TEXT)
    explanation: str = Field(default="", max_length=MAX_TEXT)
    difficulty: str = Field(default="", max_length=40)
    source_ref: str = Field(default="", max_length=500)
    knowledge_point_id: str = Field(default="", max_length=80)

    @model_validator(mode="after")
    def _consistent(self) -> "Question":
        if not _clean(self.question):
            raise ValueError("question text is empty")
        if not _clean(self.answer):
            raise ValueError("answer is empty")
        if self.type in CHOICE_TYPES:
            if len(self.options) < 2:
                raise ValueError("choice questions need at least two options")
            keys = set(self.options)
            given = {k.strip().upper() for k in re.split(r"[,\s]+", self.answer) if k.strip()}
            if not given or not given <= {k.upper() for k in keys}:
                raise ValueError("answer must name option keys, for example 'B' or 'A,C'")
            if self.type == "single_choice" and len(given) != 1:
                raise ValueError("single_choice needs exactly one answer key")
        elif self.type == "true_false":
            if self.answer.strip().lower() not in {"true", "false"}:
                raise ValueError("true_false answer must be 'true' or 'false'")
        return self


class Practice(_Model):
    questions: list[Question] = Field(default_factory=list, max_length=MAX_QUESTIONS)

    @model_validator(mode="after")
    def _unique_ids(self) -> "Practice":
        ids = [q.id for q in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("question ids must be unique")
        return self


class MasteryItem(_Model):
    id: str = Field(max_length=80)
    title: str = Field(max_length=300)
    status: MasteryStatus = "new"


class Progress(_Model):
    mastery_path: list[MasteryItem] = Field(default_factory=list, max_length=40)
    weak_areas: list[str] = Field(default_factory=list, max_length=40)
    review_due: list[str] = Field(default_factory=list, max_length=200)


class Review(_Model):
    """Generated content is a draft until a person has read it."""

    status: Literal["draft", "reviewed"] = "draft"
    reviewed_at: str = ""


class Board(_Model):
    schema_version: Literal[1] = SCHEMA_VERSION
    board_id: str
    subject: str = Field(max_length=200)
    topic: str = Field(max_length=200)
    generated_at: str = Field(default_factory=utc_now_iso)
    sources: list[Source] = Field(default_factory=list, max_length=50)
    picture: Picture = Field(default_factory=Picture)
    notes: Notes = Field(default_factory=Notes)
    practice: Practice = Field(default_factory=Practice)
    progress: Progress = Field(default_factory=Progress)
    review: Review = Field(default_factory=Review)
    warnings: list[str] = Field(default_factory=list, max_length=40)

    @field_validator("board_id")
    @classmethod
    def _board_id(cls, value: str) -> str:
        if not BOARD_ID_PATTERN.match(value):
            raise ValueError("board_id must be lowercase letters, digits and hyphens")
        return value

    @field_validator("subject", "topic")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        if not _clean(value):
            raise ValueError("must not be empty")
        return _clean(value)


__all__ = [
    "Board",
    "Formula",
    "KeyTerm",
    "MasteryItem",
    "NoteSection",
    "Notes",
    "Picture",
    "Practice",
    "Progress",
    "Question",
    "Review",
    "SCHEMA_VERSION",
    "Source",
    "slugify",
    "utc_now_iso",
]
