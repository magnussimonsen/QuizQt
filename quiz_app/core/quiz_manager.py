"""Business logic for managing quiz state shared between UI and API."""

from __future__ import annotations

from datetime import datetime
from threading import Lock

from .models import QuizQuestion, SubmittedAnswer


class QuizManager:
    """Coordinates quiz progression, active question state, and answers."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._question_counter: int = 0
        self._current_question: QuizQuestion | None = None
        self._question_active: bool = False
        self._answers: list[SubmittedAnswer] = []
        self._loaded_quiz: list[QuizQuestion] = []
        self._quiz_position: int = -1
        self._overall_answer_history: list[bool] = []

    def load_quiz_from_questions(self, questions: list[QuizQuestion]) -> None:
        """Replace the current quiz with a new ordered list of questions."""

        if not questions:
            raise ValueError("Quiz must contain at least one question.")

        with self._lock:
            sanitized = [self._prepare_question(q) for q in questions]
            self._loaded_quiz = sanitized
            self._quiz_position = -1
            self._current_question = None
            self._question_active = False
            self._answers = []
            self._overall_answer_history = []

    def set_manual_question(
        self,
        question_text: str,
        options: list[str],
        correct_option_index: int | None,
    ) -> QuizQuestion:
        """Create an ad-hoc question typed directly in the UI."""

        cleaned_text = question_text.strip()
        if not cleaned_text:
            raise ValueError("Question text must not be empty.")
        validated_options = self._validate_options(options)
        if correct_option_index is not None and not 0 <= correct_option_index < 4:
            raise ValueError("Correct option must be A, B, C, or D.")
        question = QuizQuestion(
            id=self._next_question_id(),
            question_text=cleaned_text,
            options=validated_options,
            correct_option_index=correct_option_index,
        )

        with self._lock:
            self._current_question = question
            self._question_active = True
            self._answers = []
            return question

    def move_to_next_question(self) -> QuizQuestion | None:
        """Advance to the next imported question, returning it if available."""

        with self._lock:
            if not self._loaded_quiz:
                raise RuntimeError("No quiz has been imported yet.")
            next_index = self._quiz_position + 1
            if next_index >= len(self._loaded_quiz):
                return None
            self._quiz_position = next_index
            self._current_question = self._loaded_quiz[next_index]
            self._question_active = True
            self._answers = []
            return self._current_question

    def stop_current_question(self) -> None:
        """Stop accepting answers for the active question."""
        with self._lock:
            self._question_active = False

    def record_selected_option(self, selected_option_index: int) -> SubmittedAnswer:
        """Append a student answer for the currently active question."""
        with self._lock:
            if self._current_question is None or not self._question_active:
                raise RuntimeError("No active question available.")

            if not 0 <= selected_option_index < len(self._current_question.options):
                raise ValueError("Selected option is out of range.")

            submission = SubmittedAnswer(
                question_id=self._current_question.id,
                selected_option_index=selected_option_index,
                submitted_at=datetime.utcnow(),
            )
            self._answers.append(submission)
            if self._current_question.correct_option_index is not None:
                is_correct = (
                    selected_option_index == self._current_question.correct_option_index
                )
                self._overall_answer_history.append(is_correct)
            return submission

    def get_current_question(self) -> QuizQuestion | None:
        with self._lock:
            return self._current_question

    def is_question_active(self) -> bool:
        with self._lock:
            return self._question_active

    def get_answers_for_current_question(self) -> list[SubmittedAnswer]:
        with self._lock:
            return list(self._answers)

    def has_more_quiz_questions(self) -> bool:
        with self._lock:
            return bool(self._loaded_quiz) and (self._quiz_position + 1) < len(self._loaded_quiz)

    def has_loaded_quiz(self) -> bool:
        with self._lock:
            return bool(self._loaded_quiz)

    def get_option_counts(self) -> list[int]:
        with self._lock:
            counts = [0, 0, 0, 0]
            for answer in self._answers:
                if 0 <= answer.selected_option_index < 4:
                    counts[answer.selected_option_index] += 1
            return counts

    def get_overall_correctness_percentage(self) -> float:
        with self._lock:
            if not self._overall_answer_history:
                return 0.0
            correct = sum(1 for result in self._overall_answer_history if result)
            return (correct / len(self._overall_answer_history)) * 100

    def _prepare_question(self, question: QuizQuestion) -> QuizQuestion:
        options = self._validate_options(question.options)
        if question.correct_option_index is not None and not 0 <= question.correct_option_index < 4:
            raise ValueError("Correct option index must be between 0 and 3.")
        cleaned_text = question.question_text.strip()
        if not cleaned_text:
            raise ValueError("Question text must not be empty.")
        return QuizQuestion(
            id=self._next_question_id(),
            question_text=cleaned_text,
            options=options,
            correct_option_index=question.correct_option_index,
        )

    @staticmethod
    def _validate_options(options: list[str]) -> list[str]:
        if len(options) != 4:
            raise ValueError("Each question must have exactly four options.")
        cleaned = [option.strip() for option in options]
        if any(not option for option in cleaned):
            raise ValueError("Option text cannot be empty.")
        return cleaned

    def _next_question_id(self) -> int:
        self._question_counter += 1
        return self._question_counter
