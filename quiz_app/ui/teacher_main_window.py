"""Qt main window for the teacher control panel."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
)

from quiz_app.constants.ui_constants import (
    ANSWER_REFRESH_INTERVAL_MS,
    PLACEHOLDER_QUESTION,
    STUDENT_URL_PLACEHOLDER,
    WINDOW_TITLE,
)
from quiz_app.core.quiz_manager import QuizManager


class TeacherMainWindow(QMainWindow):
    """Main Qt window the teacher uses to manage the quiz."""

    def __init__(self, quiz_manager: QuizManager, student_url: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)

        self.quiz_manager = quiz_manager
        self.student_url = student_url or STUDENT_URL_PLACEHOLDER
        self._cached_answer_count = 0

        self._build_ui()
        self._configure_refresh_timer()

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        self.student_url_label = QLabel(f"Student page: {self.student_url}")
        self.student_url_label.setWordWrap(True)
        layout.addWidget(self.student_url_label)

        self.question_input = QPlainTextEdit(self)
        self.question_input.setPlaceholderText(PLACEHOLDER_QUESTION)
        layout.addWidget(self.question_input)

        button_row = QHBoxLayout()
        self.start_button = QPushButton("Start question", self)
        self.start_button.clicked.connect(self._handle_start_question)  # type: ignore[arg-type]
        button_row.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop question", self)
        self.stop_button.clicked.connect(self._handle_stop_question)  # type: ignore[arg-type]
        button_row.addWidget(self.stop_button)
        layout.addLayout(button_row)

        self.current_question_label = QLabel("No active question.", self)
        self.current_question_label.setWordWrap(True)
        layout.addWidget(self.current_question_label)

        self.answers_list = QListWidget(self)
        layout.addWidget(self.answers_list)

    def _configure_refresh_timer(self) -> None:
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(ANSWER_REFRESH_INTERVAL_MS)
        self.refresh_timer.timeout.connect(self._refresh_state)  # type: ignore[arg-type]
        self.refresh_timer.start()

    def _handle_start_question(self) -> None:
        question_text = self.question_input.toPlainText()
        try:
            question = self.quiz_manager.set_current_question(question_text)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid question", str(exc))
            return

        self.current_question_label.setText(f"Active question: {question.question_text}")
        self.answers_list.clear()
        self._cached_answer_count = 0

    def _handle_stop_question(self) -> None:
        self.quiz_manager.stop_current_question()
        self.current_question_label.setText("Question stopped.")

    def _refresh_state(self) -> None:
        question = self.quiz_manager.get_current_question()
        if question is None or not question.is_active:
            self.current_question_label.setText("No active question.")
        else:
            self.current_question_label.setText(f"Active question: {question.question_text}")

        answers = self.quiz_manager.get_answers_for_current_question()
        if len(answers) == self._cached_answer_count:
            return

        self.answers_list.clear()
        for answer in answers:
            display = self._format_answer_display(answer.answer_text, answer.submitted_at)
            QListWidgetItem(display, self.answers_list)
        self._cached_answer_count = len(answers)

    @staticmethod
    def _format_answer_display(answer_text: str, submitted_at: datetime) -> str:
        timestamp = submitted_at.strftime("%H:%M:%S")
        return f"[{timestamp}] {answer_text}"
