"""Business logic for managing quiz state shared between UI and API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import random
from threading import Lock
from uuid import uuid4

from .models import JoinedStudent, QuizQuestion, SubmittedAnswer


@dataclass(slots=True)
class ScoreEntry:
    """Mutable scoreboard entry used internally by QuizManager."""

    display_name: str
    correct_answers: int = 0
    total_answers: int = 0
    total_answer_time_ms: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class ScoreboardRow:
    """Immutable snapshot returned to UI consumers for scoreboard display."""

    display_name: str
    correct_answers: int
    total_answers: int
    total_answer_time_ms: float


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
        self._scoreboard: dict[str, ScoreEntry] = {}
        self._current_question_aliases: set[str] = set()
        self._alias_generation: int = 0
        self._repeat_until_all_correct: bool = False
        self._rng = random.Random()
        self._lobby_open: bool = False
        self._lobby_students: dict[str, JoinedStudent] = {}
        self._lobby_generation: int = 0
        self._quiz_session_active: bool = False
        self._question_started_at: datetime | None = None

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
            self._scoreboard.clear()
            self._current_question_aliases.clear()
            self._lobby_open = False
            self._lobby_students.clear()
            self._lobby_generation = 0
            self._quiz_session_active = False
            self._question_started_at = None

    def set_repeat_until_all_correct(self, enabled: bool) -> None:
        """Toggle repeat-mode behavior for question selection."""
        with self._lock:
            self._repeat_until_all_correct = enabled

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
            is_saved=True,
        )

        with self._lock:
            self._current_question = question
            self._question_active = True
            self._answers = []
            self._current_question_aliases.clear()
            self._quiz_session_active = True
            self._question_started_at = datetime.utcnow()
            return question

    def move_to_next_question(self) -> QuizQuestion | None:
        """Advance to the next imported question, returning it if available."""

        with self._lock:
            if not self._loaded_quiz:
                raise RuntimeError("No quiz has been imported yet.")
            if self._repeat_until_all_correct:
                return self._select_unmastered_question()
            return self._advance_linear_question()

    def stop_current_question(self) -> None:
        """Stop accepting answers for the active question."""
        with self._lock:
            self._question_active = False
            self._question_started_at = None
            if self._repeat_until_all_correct:
                self._update_mastery_for_current_question()

    def record_selected_option(
        self,
        selected_option_index: int,
        display_name: str | None = None,
    ) -> SubmittedAnswer:
        """Append a student answer for the currently active question."""
        with self._lock:
            if self._current_question is None or not self._question_active:
                raise RuntimeError("No active question available.")

            if not 0 <= selected_option_index < len(self._current_question.options):
                raise ValueError("Selected option is out of range.")

            if display_name:
                if display_name in self._current_question_aliases:
                    raise RuntimeError("This student has already answered the current question.")
                self._current_question_aliases.add(display_name)

            submission = SubmittedAnswer(
                question_id=self._current_question.id,
                selected_option_index=selected_option_index,
                submitted_at=datetime.utcnow(),
                display_name=display_name,
            )
            self._answers.append(submission)
            elapsed_ms = self._compute_elapsed_answer_time(submission.submitted_at)
            if self._current_question.correct_option_index is not None:
                is_correct = selected_option_index == self._current_question.correct_option_index
                self._overall_answer_history.append(is_correct)
                if display_name:
                    self._update_scoreboard(display_name, is_correct, elapsed_ms)
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
            if not self._loaded_quiz:
                return False
            if self._repeat_until_all_correct:
                return any(not question.all_students_answered_correctly for question in self._loaded_quiz)
            return (self._quiz_position + 1) < len(self._loaded_quiz)

    def get_remaining_question_count(self) -> int:
        with self._lock:
            if not self._loaded_quiz:
                return 0
            if self._repeat_until_all_correct:
                return sum(1 for question in self._loaded_quiz if not question.all_students_answered_correctly)
            return max(0, len(self._loaded_quiz) - (self._quiz_position + 1))

    def has_loaded_quiz(self) -> bool:
        with self._lock:
            return bool(self._loaded_quiz)

    def get_loaded_questions(self) -> list[QuizQuestion]:
        """Get a copy of all loaded quiz questions."""
        with self._lock:
            return list(self._loaded_quiz)

    def has_quiz_session_started(self) -> bool:
        with self._lock:
            return self._quiz_session_active

    def quiz_is_fully_saved(self) -> bool:
        """Check if all questions in the loaded quiz have is_saved == True.
        
        Architecture note:
        Questions in QuizManager are always marked is_saved=True by _prepare_question()
        because loading them to QuizManager IS the save operation. The 'unsaved' state
        only exists at the UI level for draft questions not yet loaded to QuizManager.
        This method exists for API consistency but will always return True for loaded quizzes.
        """
        with self._lock:
            if not self._loaded_quiz:
                return True  # No quiz means nothing unsaved
            return all(question.is_saved for question in self._loaded_quiz)

    def reset_quiz(self) -> None:
        """Clear all quiz data and reset state."""
        with self._lock:
            self._loaded_quiz = []
            self._quiz_position = -1
            self._current_question = None
            self._question_active = False
            self._answers = []
            self._overall_answer_history = []
            self._scoreboard.clear()
            self._current_question_aliases.clear()
            self._alias_generation = 0
            self._quiz_session_active = False
            self._question_started_at = None

    def reset_quiz_progress(self) -> None:
        """Reset live progression so the next session starts from the first question."""
        with self._lock:
            self._quiz_position = -1
            self._current_question = None
            self._question_active = False
            self._answers = []
            self._overall_answer_history = []
            self._current_question_aliases.clear()
            for question in self._loaded_quiz:
                question.all_students_answered_correctly = False
            self._lobby_students.clear()
            self._lobby_open = False
            self._quiz_session_active = False
            self._question_started_at = None
        
    def begin_lobby_session(self) -> None:
        """Open the lobby so students can join the upcoming quiz."""
        with self._lock:
            self._lobby_open = True
            self._lobby_generation += 1
            self._lobby_students.clear()

    def cancel_lobby_session(self) -> None:
        """Close the lobby and discard any pending students."""
        with self._lock:
            self._lobby_open = False
            self._lobby_students.clear()

    def lobby_is_open(self) -> bool:
        with self._lock:
            return self._lobby_open

    def register_lobby_student(self, display_name: str) -> JoinedStudent:
        """Track a student who indicated readiness during the lobby phase."""
        with self._lock:
            if not self._lobby_open:
                raise RuntimeError("Lobby is not currently open.")
            entry = self._lobby_students.get(display_name)
            if entry is None:
                entry = JoinedStudent(
                    student_id=uuid4().hex,
                    display_name=display_name,
                    joined_at=datetime.utcnow(),
                )
                self._lobby_students[display_name] = entry
            return entry

    def get_lobby_students(self) -> list[JoinedStudent]:
        """Return a chronological list of students ready in the lobby."""
        with self._lock:
            return sorted(self._lobby_students.values(), key=lambda student: student.joined_at)

    def finalize_lobby_students(self) -> list[JoinedStudent]:
        """Freeze lobby participants and close the lobby."""
        with self._lock:
            snapshot = sorted(self._lobby_students.values(), key=lambda student: student.joined_at)
            self._lobby_students.clear()
            self._lobby_open = False
            return snapshot

    def get_lobby_generation(self) -> int:
        with self._lock:
            return self._lobby_generation

    def add_question(self, question: QuizQuestion) -> None:
        """Add a new question to the end of the quiz."""
        with self._lock:
            prepared = self._prepare_question(question)
            self._loaded_quiz.append(prepared)

    def update_question(self, index: int, question: QuizQuestion) -> None:
        """Update a question at the specified index."""
        with self._lock:
            if not 0 <= index < len(self._loaded_quiz):
                raise IndexError(f"Question index {index} out of range")
            prepared = self._prepare_question(question)
            # Preserve the original ID
            prepared = QuizQuestion(
                id=self._loaded_quiz[index].id,
                question_text=prepared.question_text,
                options=prepared.options,
                correct_option_index=prepared.correct_option_index,
                is_saved=prepared.is_saved,
            )
            self._loaded_quiz[index] = prepared

    def delete_question(self, index: int) -> None:
        """Delete a question at the specified index."""
        with self._lock:
            if not 0 <= index < len(self._loaded_quiz):
                raise IndexError(f"Question index {index} out of range")
            self._loaded_quiz.pop(index)

    def get_question_count(self) -> int:
        """Get the number of questions in the quiz."""
        with self._lock:
            return len(self._loaded_quiz)

    def get_question_at_index(self, index: int) -> QuizQuestion:
        """Get a question at the specified index."""
        with self._lock:
            if not 0 <= index < len(self._loaded_quiz):
                raise IndexError(f"Question index {index} out of range")
            return self._loaded_quiz[index]

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

    def reset_student_aliases(self) -> int:
        """Advance the alias generation so clients refresh their display names."""
        with self._lock:
            self._alias_generation += 1
            self._scoreboard.clear()
            self._current_question_aliases.clear()
            return self._alias_generation

    def get_alias_generation(self) -> int:
        """Get the current alias generation identifier."""
        with self._lock:
            return self._alias_generation

    def get_top_scorers(self, limit: int) -> list[ScoreboardRow]:
        with self._lock:
            limit = max(0, limit)
            entries = sorted(
                self._scoreboard.values(),
                key=lambda entry: (
                    -entry.correct_answers,
                    entry.total_answers,
                    entry.total_answer_time_ms,
                    entry.last_updated,
                ),
            )
            snapshot: list[ScoreboardRow] = []
            for entry in entries[:limit]:
                snapshot.append(
                    ScoreboardRow(
                        display_name=entry.display_name,
                        correct_answers=entry.correct_answers,
                        total_answers=entry.total_answers,
                        total_answer_time_ms=entry.total_answer_time_ms,
                    )
                )
            return snapshot

    def _update_scoreboard(self, display_name: str, is_correct: bool, elapsed_ms: float) -> None:
        entry = self._scoreboard.get(display_name)
        if entry is None:
            entry = ScoreEntry(display_name=display_name)
            self._scoreboard[display_name] = entry
        entry.total_answers += 1
        if is_correct:
            entry.correct_answers += 1
        entry.total_answer_time_ms += max(0.0, elapsed_ms)
        entry.last_updated = datetime.utcnow()

    def _compute_elapsed_answer_time(self, submitted_at: datetime) -> float:
        if self._question_started_at is None:
            return 0.0
        elapsed = submitted_at - self._question_started_at
        return max(0.0, elapsed.total_seconds() * 1000.0)

    def _advance_linear_question(self) -> QuizQuestion | None:
        next_index = self._quiz_position + 1
        if next_index >= len(self._loaded_quiz):
            return None
        self._quiz_position = next_index
        self._current_question = self._loaded_quiz[next_index]
        self._question_active = True
        self._answers = []
        self._current_question_aliases.clear()
        self._quiz_session_active = True
        self._question_started_at = datetime.utcnow()
        return self._current_question

    def _select_unmastered_question(self) -> QuizQuestion | None:
        candidates = [idx for idx, question in enumerate(self._loaded_quiz) if not question.all_students_answered_correctly]
        if not candidates:
            self._current_question = None
            self._question_active = False
            return None
        next_index = self._rng.choice(candidates)
        self._quiz_position = next_index
        self._current_question = self._loaded_quiz[next_index]
        self._question_active = True
        self._answers = []
        self._current_question_aliases.clear()
        self._quiz_session_active = True
        self._question_started_at = datetime.utcnow()
        return self._current_question

    def _update_mastery_for_current_question(self) -> None:
        if self._current_question is None:
            return
        if self._quiz_position < 0 or self._quiz_position >= len(self._loaded_quiz):
            return
        question = self._loaded_quiz[self._quiz_position]
        if question.correct_option_index is None:
            question.all_students_answered_correctly = True
            return
        if not self._answers:
            question.all_students_answered_correctly = False
            return
        question.all_students_answered_correctly = all(
            answer.selected_option_index == question.correct_option_index for answer in self._answers
        )

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
            is_saved=True,
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
