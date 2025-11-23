"""Service for managing the active quiz session and question state."""

from __future__ import annotations

from datetime import datetime
import random
from uuid import uuid4

from quiz_app.core.models import QuizQuestion, SubmittedAnswer


class GameSession:
    """Manages the state of an active quiz game."""

    def __init__(self) -> None:
        self._active: bool = False
        self._current_question: QuizQuestion | None = None
        self._question_active: bool = False
        self._question_started_at: datetime | None = None
        self._answers: list[SubmittedAnswer] = []
        self._current_question_aliases: set[str] = set()
        self._alias_generation: int = 0
        self._quiz_position: int = -1
        
        # Shuffle state
        self._shuffle_rng = random.Random()
        self._current_shuffled_options: list[str] = []
        self._shuffled_correct_option_index: int | None = None
        self._current_option_order: list[int] | None = None

    def start_session(self) -> None:
        self._active = True
        self._quiz_position = -1
        self.reset_question_state()

    def stop_session(self) -> None:
        self._active = False
        self.reset_question_state()

    def is_active(self) -> bool:
        return self._active

    def reset_question_state(self) -> None:
        self._current_question = None
        self._question_active = False
        self._question_started_at = None
        self._answers = []
        self._current_question_aliases.clear()
        self._current_shuffled_options = []
        self._shuffled_correct_option_index = None
        self._current_option_order = None

    def start_question(self, question: QuizQuestion) -> None:
        self._current_question = question
        self._question_active = True
        self._question_started_at = datetime.utcnow()
        self._answers = []
        self._current_question_aliases.clear()
        self._shuffle_options(question)

    def stop_question(self) -> None:
        self._question_active = False

    def is_question_active(self) -> bool:
        return self._question_active

    def get_current_question(self) -> QuizQuestion | None:
        return self._current_question

    def get_question_start_time(self) -> datetime | None:
        return self._question_started_at

    def record_answer(self, student_name: str, option_index: int) -> bool:
        """Record an answer. Returns True if it's a new answer, False if update."""
        if not self._question_active or not self._current_question:
            return False

        # Map shuffled index back to original index if needed
        original_index = option_index
        if self._current_option_order:
            if 0 <= option_index < len(self._current_option_order):
                original_index = self._current_option_order[option_index]

        is_correct = (original_index == self._current_question.correct_option_index)
        
        # Check if student already answered
        existing_index = next((i for i, a in enumerate(self._answers) if a.student_id == student_name), -1)
        
        answer = SubmittedAnswer(
            question_id=self._current_question.id,
            selected_option_index=original_index,
            submitted_at=datetime.utcnow(),
            is_correct=is_correct,
            student_id=student_name,
            display_name=student_name,
        )

        if existing_index >= 0:
            self._answers[existing_index] = answer
            return False
        else:
            self._answers.append(answer)
            return True

    def get_answers(self) -> list[SubmittedAnswer]:
        return list(self._answers)

    def get_answer_count(self) -> int:
        return len(self._answers)

    def has_student_answered(self, student_name: str) -> bool:
        return any(a.student_id == student_name for a in self._answers)

    def set_shuffle_seed(self, seed: int | None) -> None:
        self._shuffle_rng.seed(seed)

    def get_display_options(self) -> list[str]:
        if self._current_question:
            return self._current_shuffled_options or self._current_question.options
        return []

    def get_display_correct_index(self) -> int | None:
        if self._current_question:
             return self._shuffled_correct_option_index if self._shuffled_correct_option_index is not None else self._current_question.correct_option_index
        return None

    def _shuffle_options(self, question: QuizQuestion) -> None:
        options = list(question.options)
        indices = list(range(len(options)))
        
        # Shuffle
        combined = list(zip(options, indices))
        self._shuffle_rng.shuffle(combined)
        
        self._current_shuffled_options = [item[0] for item in combined]
        self._current_option_order = [item[1] for item in combined]
        
        # Find new correct index
        if question.correct_option_index is not None:
            try:
                self._shuffled_correct_option_index = self._current_option_order.index(question.correct_option_index)
            except ValueError:
                self._shuffled_correct_option_index = None
        else:
            self._shuffled_correct_option_index = None

    def get_alias_generation(self) -> int:
        return self._alias_generation

    def advance_alias_generation(self) -> None:
        self._alias_generation += 1
        self._current_question_aliases.clear()

    def register_alias(self, alias: str) -> None:
        self._current_question_aliases.add(alias)

    def has_alias(self, alias: str) -> bool:
        return alias in self._current_question_aliases
