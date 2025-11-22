"""Service for managing the collection of quiz questions."""

from __future__ import annotations

from quiz_app.core.models import QuizQuestion


class QuizRepository:
    """Manages the lifecycle and storage of quiz questions."""

    def __init__(self) -> None:
        self._questions: list[QuizQuestion] = []
        self._question_counter: int = 0

    def load_questions(self, questions: list[QuizQuestion]) -> None:
        """Replace the current quiz with a new list of questions."""
        if not questions:
            raise ValueError("Quiz must contain at least one question.")
        
        self._questions = [self._prepare_question(q) for q in questions]

    def get_questions(self) -> list[QuizQuestion]:
        """Return a copy of all loaded questions."""
        return list(self._questions)

    def has_questions(self) -> bool:
        return bool(self._questions)

    def get_question_count(self) -> int:
        return len(self._questions)

    def get_question_at_index(self, index: int) -> QuizQuestion:
        if not 0 <= index < len(self._questions):
            raise IndexError(f"Question index {index} out of range")
        return self._questions[index]

    def add_question(self, question: QuizQuestion) -> None:
        prepared = self._prepare_question(question)
        self._questions.append(prepared)

    def update_question(self, index: int, question: QuizQuestion) -> None:
        if not 0 <= index < len(self._questions):
            raise IndexError(f"Question index {index} out of range")
        
        prepared = self._prepare_question(question)
        # Preserve the original ID
        prepared = QuizQuestion(
            id=self._questions[index].id,
            question_text=prepared.question_text,
            options=prepared.options,
            time_limit_seconds=prepared.time_limit_seconds,
            correct_option_index=prepared.correct_option_index,
            is_saved=prepared.is_saved,
        )
        self._questions[index] = prepared

    def delete_question(self, index: int) -> None:
        if not 0 <= index < len(self._questions):
            raise IndexError(f"Question index {index} out of range")
        self._questions.pop(index)

    def clear(self) -> None:
        self._questions = []

    def are_all_saved(self) -> bool:
        if not self._questions:
            return True
        return all(question.is_saved for question in self._questions)

    def _prepare_question(self, question: QuizQuestion) -> QuizQuestion:
        """Validate and normalize a question before storage."""
        options = self._validate_options(question.options)
        if question.correct_option_index is not None and not 0 <= question.correct_option_index < 4:
            raise ValueError("Correct option index must be between 0 and 3.")
        
        cleaned_text = question.question_text.strip()
        if not cleaned_text:
            raise ValueError("Question text must not be empty.")
        
        normalized_time_limit = self._normalize_time_limit(question.time_limit_seconds)
        
        return QuizQuestion(
            id=self._next_question_id(),
            question_text=cleaned_text,
            options=options,
            time_limit_seconds=normalized_time_limit,
            correct_option_index=question.correct_option_index,
            is_saved=True,
        )

    def _next_question_id(self) -> int:
        self._question_counter += 1
        return self._question_counter

    @staticmethod
    def _validate_options(options: list[str]) -> list[str]:
        if len(options) != 4:
            raise ValueError("Each question must have exactly four options.")
        cleaned = [option.strip() for option in options]
        if any(not option for option in cleaned):
            raise ValueError("Option text cannot be empty.")
        return cleaned

    @staticmethod
    def _normalize_time_limit(time_limit_seconds: int | None) -> int | None:
        if time_limit_seconds is None:
            return None
        if not isinstance(time_limit_seconds, int):
            raise ValueError("Time limit must be provided as an integer number of seconds.")
        if time_limit_seconds <= 0:
            raise ValueError("Time limit must be a positive integer.")
        return time_limit_seconds
