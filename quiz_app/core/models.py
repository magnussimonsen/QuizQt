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
    time_limit_seconds: int | None = None
    question_started_at: datetime | None = None  # Track presentation time for analytics
    correct_option_index: int | None = None
    is_saved: bool = True
    all_students_answered_correctly: bool = False


@dataclass(slots=True)
class SubmittedAnswer:
    """Represents a selected option submitted by a student."""

    question_id: int
    selected_option_index: int
    submitted_at: datetime
    is_correct: bool
    student_id: str  # This was display_name in some contexts, but let's be explicit.
    display_name: str | None = None


@dataclass(slots=True)
class JoinedStudent:
    """Represents a student who confirmed readiness in the lobby."""

    student_id: str
    display_name: str
    joined_at: datetime
