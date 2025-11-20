"""Domain models for the quiz application."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class QuizQuestion:
    """Multiple-choice quiz question with exactly four options."""

    id: int
    question_text: str
    options: list[str]
    correct_option_index: int | None = None
    is_saved: bool = True
    all_students_answered_correctly: bool = False


@dataclass(slots=True)
class SubmittedAnswer:
    """Represents a selected option submitted by a student."""

    question_id: int
    selected_option_index: int
    submitted_at: datetime
    display_name: str | None = None
