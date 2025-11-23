"""Business logic for managing quiz state shared between UI and API."""

from __future__ import annotations

from datetime import datetime
from threading import Lock

from quiz_app.core.models import JoinedStudent, QuizQuestion, SubmittedAnswer
from quiz_app.core.services.game_session import GameSession
from quiz_app.core.services.lobby_manager import LobbyManager
from quiz_app.core.services.quiz_repository import QuizRepository
from quiz_app.core.services.scoreboard import Scoreboard, ScoreboardRow


class QuizManager:
    """Facade for quiz services: Repository, Lobby, Scoreboard, and GameSession."""

    def __init__(self) -> None:
        self._lock = Lock()
        
        # Services
        self._repository = QuizRepository()
        self._lobby = LobbyManager()
        self._scoreboard = Scoreboard()
        self._session = GameSession()
        
        # Legacy state mapping (for compatibility if needed, but mostly replaced)
        self._repeat_until_all_correct: bool = False

    # --- Quiz Repository Delegation ---

    def load_quiz_from_questions(self, questions: list[QuizQuestion]) -> None:
        with self._lock:
            self._repository.load_questions(questions)
            self._session.stop_session()
            self._lobby.close_lobby()
            self._scoreboard.clear()

    def get_loaded_questions(self) -> list[QuizQuestion]:
        with self._lock:
            return self._repository.get_questions()

    def has_loaded_quiz(self) -> bool:
        with self._lock:
            return self._repository.has_questions()

    def get_question_count(self) -> int:
        with self._lock:
            return self._repository.get_question_count()

    def get_question_at_index(self, index: int) -> QuizQuestion:
        with self._lock:
            return self._repository.get_question_at_index(index)

    def add_question(self, question: QuizQuestion) -> None:
        with self._lock:
            self._repository.add_question(question)

    def update_question(self, index: int, question: QuizQuestion) -> None:
        with self._lock:
            self._repository.update_question(index, question)

    def delete_question(self, index: int) -> None:
        with self._lock:
            self._repository.delete_question(index)

    def reset_quiz(self) -> None:
        with self._lock:
            self._repository.clear()
            self._session.stop_session()
            self._lobby.close_lobby()
            self._scoreboard.clear()

    def check_unsaved_changes(self) -> bool:
        with self._lock:
            return not self._repository.are_all_saved()

    # --- Lobby Delegation ---

    def begin_lobby_session(self) -> None:
        with self._lock:
            self._lobby.open_lobby()
            self._session.stop_session()
            self._scoreboard.clear()

    def cancel_lobby_session(self) -> None:
        with self._lock:
            self._lobby.close_lobby()

    def is_lobby_open(self) -> bool:
        with self._lock:
            return self._lobby.is_open()

    def join_lobby(self, display_name: str) -> JoinedStudent:
        with self._lock:
            return self._lobby.register_student(display_name)

    def get_lobby_students(self) -> list[JoinedStudent]:
        with self._lock:
            return self._lobby.get_students()

    def finalize_lobby_students(self) -> None:
        with self._lock:
            students = self._lobby.finalize_students()
            display_names = {s.display_name for s in students}
            self._scoreboard.initialize_students(display_names)

    def get_lobby_generation(self) -> int:
        with self._lock:
            return self._lobby.get_generation()

    def has_quiz_session_started(self) -> bool:
        with self._lock:
            return self._session.is_active()

    # --- Game Session Delegation ---

    def reset_quiz_progress(self) -> None:
        with self._lock:
            self._session.start_session()
            # Note: We don't clear scoreboard here to allow cumulative scores across rounds if desired,
            # but typically a reset implies clearing. For now, let's keep scoreboard.
            # If "reset" means "start over", maybe we should clear scores? 
            # The original implementation cleared scores on load_quiz but not necessarily on reset_progress.
            # Let's stick to session reset.

    def move_to_next_question(self) -> QuizQuestion | None:
        with self._lock:
            # Simple linear progression for now
            current_q = self._session.get_current_question()
            questions = self._repository.get_questions()
            
            next_index = 0
            if current_q:
                try:
                    current_index = questions.index(current_q) # This relies on object identity or equality
                    # Since repository returns copies or new instances, this might fail if not careful.
                    # Ideally we track index.
                    # Let's use ID matching.
                    current_index = next((i for i, q in enumerate(questions) if q.id == current_q.id), -1)
                    next_index = current_index + 1
                except ValueError:
                    next_index = 0
            
            if next_index < len(questions):
                next_q = questions[next_index]
                self._session.start_question(next_q)
                return next_q
            
            self._session.stop_question()
            return None

    def stop_current_question(self) -> None:
        with self._lock:
            self._session.stop_question()

    def get_current_question(self) -> QuizQuestion | None:
        with self._lock:
            return self._session.get_current_question()

    def is_question_active(self) -> bool:
        with self._lock:
            return self._session.is_question_active()

    def get_current_question_start_time(self) -> datetime | None:
        with self._lock:
            return self._session.get_question_start_time()

    def submit_answer(self, student_name: str, option_index: int) -> SubmittedAnswer:
        with self._lock:
            # Check if student is in session
            if student_name not in self._lobby.get_session_students():
                # Allow late joiners? Original code didn't explicitly forbid it but implied lobby flow.
                # For now, strict mode: must be in session.
                # Actually, original code allowed anyone with a name.
                pass

            is_new = self._session.record_answer(student_name, option_index)
            
            # Retrieve the submitted answer object
            answers = self._session.get_answers()
            # Find the answer for this student (it must exist now)
            submitted = next((a for a in answers if a.student_id == student_name), None)
            if not submitted:
                 raise RuntimeError("Answer recorded but not found.")

            if is_new:
                # Update scoreboard
                # We need to know if it was correct and the time taken
                start_time = self._session.get_question_start_time()
                time_ms = 0.0
                if start_time:
                    time_ms = (submitted.submitted_at - start_time).total_seconds() * 1000
                
                self._scoreboard.record_answer(student_name, submitted.is_correct, time_ms)
            
            return submitted

    def get_answers_for_current_question(self) -> list[SubmittedAnswer]:
        with self._lock:
            return self._session.get_answers()

    def get_option_counts(self) -> list[int]:
        with self._lock:
            answers = self._session.get_answers()
            counts = [0, 0, 0, 0]
            for answer in answers:
                if 0 <= answer.selected_option_index < 4:
                    counts[answer.selected_option_index] += 1
            return counts

    def get_overall_correctness_percentage(self) -> float:
        with self._lock:
            answers = self._session.get_answers()
            if not answers:
                return 0.0
            correct_count = sum(1 for a in answers if a.is_correct)
            return (correct_count / len(answers)) * 100

    def get_remaining_question_count(self) -> int:
        with self._lock:
            total = self._repository.get_question_count()
            current_q = self._session.get_current_question()
            if not current_q:
                return total
            
            questions = self._repository.get_questions()
            try:
                current_index = next((i for i, q in enumerate(questions) if q.id == current_q.id), -1)
                return max(0, total - (current_index + 1))
            except ValueError:
                return 0

    # --- Scoreboard Delegation ---

    def get_top_scorers(self, limit: int) -> list[ScoreboardRow]:
        with self._lock:
            return self._scoreboard.get_top_scorers(limit)

    # --- Settings & Misc ---

    def set_repeat_until_all_correct(self, enabled: bool) -> None:
        with self._lock:
            self._repeat_until_all_correct = enabled

    def set_shuffle_seed(self, seed: int | None) -> None:
        with self._lock:
            self._session.set_shuffle_seed(seed)

    def get_current_display_options(self) -> list[str]:
        with self._lock:
            return self._session.get_display_options()

    def get_current_display_correct_index(self) -> int | None:
        with self._lock:
            return self._session.get_display_correct_index()

    # --- Alias Management (Legacy/Session) ---

    def get_alias_generation(self) -> int:
        with self._lock:
            return self._session.get_alias_generation()

    # Backwards-compat helper for any legacy callers
    def get_student_alias_generation(self) -> int:  # pragma: no cover - legacy alias
        return self.get_alias_generation()

    def register_student_alias(self, alias: str) -> None:
        with self._lock:
            self._session.register_alias(alias)

    def has_student_alias(self, alias: str) -> bool:
        with self._lock:
            return self._session.has_alias(alias)
    
    def reset_student_aliases(self) -> None:
        with self._lock:
            self._session.advance_alias_generation()
