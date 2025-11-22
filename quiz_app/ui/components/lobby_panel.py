"""Component for the student lobby waiting room."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from quiz_app.constants.ui_constants import (
    MODE4_ACTION_BUTTON,
    MODE4_DESCRIPTION,
    MODE4_EMPTY_STATE,
    MODE4_READY_COUNT_TEMPLATE,
)
from quiz_app.core.quiz_manager import QuizManager
from quiz_app.ui.dialog_helpers import show_warning
from quiz_app.styling.styles import Styles


class LobbyPanel(QWidget):
    """UI component for managing the student lobby."""

    def __init__(
        self, 
        quiz_manager: QuizManager, 
        student_url: str, 
        on_start_quiz: callable,
        on_cancel: callable,
        parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.quiz_manager = quiz_manager
        self.student_url = student_url
        self.on_start_quiz = on_start_quiz
        self.on_cancel = on_cancel
        self._lobby_snapshot_ids: list[str] = []
        
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.description_label = QLabel(MODE4_DESCRIPTION, self)
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        self.network_label = QLabel(f"Students connect to: {self.student_url}", self)
        self.network_label.setWordWrap(True)
        self.network_label.setStyleSheet(Styles.get_large_label_style())
        layout.addWidget(self.network_label)

        self.ready_label = QLabel(MODE4_READY_COUNT_TEMPLATE.format(count=0), self)
        layout.addWidget(self.ready_label)

        self.participant_list = QListWidget(self)
        self.participant_list.setAlternatingRowColors(True)
        layout.addWidget(self.participant_list, stretch=1)

        self.empty_label = QLabel(MODE4_EMPTY_STATE, self)
        self.empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty_label)

        self.start_button = QPushButton(MODE4_ACTION_BUTTON, self)
        self.start_button.clicked.connect(self._handle_start_click)
        layout.addWidget(self.start_button)

    def _handle_start_click(self) -> None:
        if self.participant_list.count() == 0:
            show_warning(self, "No students", "Wait for at least one student to join before starting the quiz.")
            return
        self.on_start_quiz()

    def refresh_participants(self) -> None:
        students = self.quiz_manager.get_lobby_students()
        snapshot = [student.student_id for student in students]
        if snapshot == self._lobby_snapshot_ids:
            return
        self._lobby_snapshot_ids = snapshot
        self.participant_list.clear()
        for student in students:
            timestamp = student.joined_at.strftime("%H:%M:%S")
            QListWidgetItem(f"{student.display_name} — Ready at {timestamp}", self.participant_list)
        count = len(students)
        self.ready_label.setText(MODE4_READY_COUNT_TEMPLATE.format(count=count))
        self.empty_label.setVisible(count == 0)

    def reset_state(self) -> None:
        self._lobby_snapshot_ids = []
        self.participant_list.clear()
        self.ready_label.setText(MODE4_READY_COUNT_TEMPLATE.format(count=0))
        self.empty_label.setText(MODE4_EMPTY_STATE)
        self.empty_label.setVisible(True)

    def update_student_url(self, url: str) -> None:
        self.student_url = url
        self.network_label.setText(f"Students connect to: {url}")

    def apply_font_size(self, font_size: int) -> None:
        self.start_button.setStyleSheet(f"font-size: {font_size}pt;")
        self.participant_list.setStyleSheet(f"font-size: {font_size}pt;")
        self.network_label.setStyleSheet(f"font-size: {font_size}pt; font-weight: bold;")
