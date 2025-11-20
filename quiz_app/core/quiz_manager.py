"""Business logic for managing quiz state shared between UI and API."""

from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import List, Optional

from .models import Question, SubmittedAnswer


class QuizManager:
    """Coordinates the active question and tracks submitted answers."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._current_question: Optional[Question] = None
        self._answers: list[SubmittedAnswer] = []
        self._question_counter: int = 0

    def set_current_question(self, question_text: str) -> Question:
        """Start a new question and reset any previous answers."""
        cleaned_text = question_text.strip()
        if not cleaned_text:
            raise ValueError("Question text must not be empty.")

        with self._lock:
            self._question_counter += 1
            self._current_question = Question(
                id=self._question_counter,
                question_text=cleaned_text,
                is_active=True,
            )
            self._answers = []
            return self._current_question

    def stop_current_question(self) -> None:
        """Stop the current question so no more answers are accepted."""
        with self._lock:
            if self._current_question is not None:
                self._current_question.is_active = False
            # Keep the question reference for UI display but mark inactive.

    def add_answer(self, answer_text: str) -> SubmittedAnswer:
        """Add an answer for the active question, raising if none is active."""
        cleaned_answer = answer_text.strip()
        if not cleaned_answer:
            raise ValueError("Answer text must not be empty.")

        with self._lock:
            if self._current_question is None or not self._current_question.is_active:
                raise RuntimeError("No active question available.")

            submitted_answer = SubmittedAnswer(
                question_id=self._current_question.id,
                answer_text=cleaned_answer,
                submitted_at=datetime.utcnow(),
            )
            self._answers.append(submitted_answer)
            return submitted_answer

    def get_current_question(self) -> Optional[Question]:
        """Return the current question (if any)."""
        with self._lock:
            return self._current_question

    def get_answers_for_current_question(self) -> List[SubmittedAnswer]:
        """Return a snapshot of the answers for the active question."""
        with self._lock:
            return list(self._answers)
