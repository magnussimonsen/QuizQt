"""Service for managing quiz scores and statistics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class ScoreEntry:
    """Mutable scoreboard entry used internally."""

    display_name: str
    correct_answers: int = 0
    total_answers: int = 0
    total_answer_time_ms: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class ScoreboardRow:
    """Immutable snapshot returned to consumers."""

    display_name: str
    correct_answers: int
    total_answers: int
    total_answer_time_ms: float


class Scoreboard:
    """Tracks and manages student scores."""

    def __init__(self) -> None:
        self._scores: dict[str, ScoreEntry] = {}

    def record_answer(self, display_name: str, is_correct: bool, answer_time_ms: float) -> None:
        """Update the score for a student."""
        entry = self._scores.get(display_name)
        if entry is None:
            entry = ScoreEntry(display_name=display_name)
            self._scores[display_name] = entry

        entry.total_answers += 1
        if is_correct:
            entry.correct_answers += 1
        entry.total_answer_time_ms += answer_time_ms
        entry.last_updated = datetime.utcnow()

    def get_top_scorers(self, limit: int = 3) -> list[ScoreboardRow]:
        """Return the top N scorers sorted by correct answers and time."""
        sorted_entries = sorted(
            self._scores.values(),
            key=lambda e: (-e.correct_answers, e.total_answer_time_ms),
        )
        
        return [
            ScoreboardRow(
                display_name=entry.display_name,
                correct_answers=entry.correct_answers,
                total_answers=entry.total_answers,
                total_answer_time_ms=entry.total_answer_time_ms,
            )
            for entry in sorted_entries[:limit]
        ]

    def clear(self) -> None:
        """Reset all scores."""
        self._scores.clear()

    def initialize_students(self, display_names: set[str]) -> None:
        """Initialize score entries for a set of students."""
        self.clear()
        for name in display_names:
            self._scores[name] = ScoreEntry(display_name=name)
