"""Service for managing student connections and the lobby state."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from quiz_app.core.models import JoinedStudent


class LobbyManager:
    """Manages the lobby waiting room and student registration."""

    def __init__(self) -> None:
        self._lobby_open: bool = False
        self._lobby_students: dict[str, JoinedStudent] = {}
        self._lobby_generation: int = 0
        self._session_students: set[str] = set()

    def open_lobby(self) -> None:
        """Open the lobby for new students."""
        self._lobby_open = True
        self._lobby_generation += 1
        self._lobby_students.clear()
        self._session_students.clear()

    def close_lobby(self) -> None:
        """Close the lobby and stop accepting new students."""
        self._lobby_open = False
        self._lobby_students.clear()
        self._session_students.clear()

    def is_open(self) -> bool:
        return self._lobby_open

    def register_student(self, display_name: str) -> JoinedStudent:
        """Register a student in the lobby."""
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

    def get_students(self) -> list[JoinedStudent]:
        """Return a list of students currently in the lobby."""
        return sorted(self._lobby_students.values(), key=lambda s: s.joined_at)

    def finalize_students(self) -> list[JoinedStudent]:
        """Close the lobby and return the final list of participants."""
        snapshot = self.get_students()
        self._lobby_students.clear()
        self._lobby_open = False
        self._session_students = {student.display_name for student in snapshot}
        return snapshot

    def get_session_students(self) -> set[str]:
        """Return the set of display names for students in the current session."""
        return set(self._session_students)

    def get_generation(self) -> int:
        return self._lobby_generation

    def clear_session(self) -> None:
        self._session_students.clear()
