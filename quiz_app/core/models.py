"""Domain models for the quiz application."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Question:
    """Represents a question that can be shown to students."""

    id: int
    question_text: str
    is_active: bool = True


@dataclass(slots=True)
class SubmittedAnswer:
    """Represents an answer submitted by a student for a question."""

    question_id: int
    answer_text: str
    submitted_at: datetime
