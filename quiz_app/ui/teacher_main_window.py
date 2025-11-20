"""Qt main window implementing creation/import/live quiz modes."""

from __future__ import annotations

from enum import Enum, auto
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QComboBox,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from quiz_app.constants.ui_constants import (
    ANSWER_REFRESH_INTERVAL_MS,
    IMPORT_BUTTON_TEXT,
    IMPORT_DIALOG_TITLE,
    IMPORT_FILE_FILTER,
    MODE1_DELETE_BUTTON,
    MODE1_INSERT_BUTTON,
    MODE1_NEXT_BUTTON,
    MODE1_PREV_BUTTON,
    MODE1_SAVE_ALL_BUTTON,
    MODE1_SAVE_BUTTON,
    MODE3_NEXT_QUESTION,
    MODE3_SHOW_CORRECT,
    MODE_BUTTON_IMPORT,
    MODE_BUTTON_MAKE,
    MODE_BUTTON_START,
    MODE_BUTTON_STOP,
    NO_QUIZ_LOADED_MESSAGE,
    PLACEHOLDER_QUESTION,
    QUIZ_COMPLETE_MESSAGE,
    QUIZ_SAVED_MESSAGE,
    STUDENT_URL_PLACEHOLDER,
    WINDOW_TITLE,
)
from quiz_app.core.markdown_math_renderer import renderer
from quiz_app.core.models import QuizQuestion
from quiz_app.core.quiz_importer import QuizImportError, load_quiz_from_file
from quiz_app.core.quiz_manager import QuizManager


class TeacherMode(Enum):
    """High-level UI mode for the teacher console."""

    QUIZ_CREATION = auto()
    QUIZ_IMPORT = auto()
    QUIZ_LIVE = auto()


class LiveAction(Enum):
    """The next action the live-mode toggle button will perform."""

    SHOW_CORRECT = auto()
    LOAD_NEXT = auto()


class TeacherMainWindow(QMainWindow):
    """Main Qt window orchestrating the three application modes."""

    def __init__(self, quiz_manager: QuizManager, student_url: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)

        self.quiz_manager = quiz_manager
        self.student_url = student_url or STUDENT_URL_PLACEHOLDER

        self._mode = TeacherMode.QUIZ_CREATION
        self._draft_questions: list[QuizQuestion] = []
        self._current_draft_index: int = -1
        self._live_session_active = False
        self._live_action = LiveAction.SHOW_CORRECT

        self._build_ui()
        self._configure_refresh_timer()
        self._refresh_creation_preview()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout()
        central_widget.setLayout(root_layout)

        self._build_mode_buttons(root_layout)

        # QStackedWidget keeps each mode isolated. We considered manual hide/show but
        # the stacked approach reduces bookkeeping while still allowing lazy widget
        # construction. If later we add more modes, simply append another page.
        self.mode_stack = QStackedWidget(self)
        self.mode_stack.addWidget(self._build_mode1_creation_panel())
        self.mode_stack.addWidget(self._build_mode2_import_panel())
        self.mode_stack.addWidget(self._build_mode3_live_panel())
        root_layout.addWidget(self.mode_stack)

        self._set_mode(TeacherMode.QUIZ_CREATION)

    def _build_mode_buttons(self, layout: QVBoxLayout) -> None:
        button_row = QHBoxLayout()

        self.make_mode_button = QPushButton(MODE_BUTTON_MAKE, self)
        self.make_mode_button.setCheckable(True)
        self.make_mode_button.clicked.connect(lambda: self._set_mode(TeacherMode.QUIZ_CREATION))  # type: ignore[arg-type]
        button_row.addWidget(self.make_mode_button)

        self.import_mode_button = QPushButton(MODE_BUTTON_IMPORT, self)
        self.import_mode_button.setCheckable(True)
        self.import_mode_button.clicked.connect(lambda: self._set_mode(TeacherMode.QUIZ_IMPORT))  # type: ignore[arg-type]
        button_row.addWidget(self.import_mode_button)

        self.start_mode_button = QPushButton(MODE_BUTTON_START, self)
        self.start_mode_button.setCheckable(True)
        self.start_mode_button.clicked.connect(self._handle_start_mode_button)  # type: ignore[arg-type]
        button_row.addWidget(self.start_mode_button)

        layout.addLayout(button_row)

    def _build_mode1_creation_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout()
        panel.setLayout(layout)

        action_row = QHBoxLayout()
        self.creation_insert_button = QPushButton(MODE1_INSERT_BUTTON, self)
        self.creation_insert_button.clicked.connect(self._handle_insert_new_draft)  # type: ignore[arg-type]
        action_row.addWidget(self.creation_insert_button)

        self.creation_save_button = QPushButton(MODE1_SAVE_BUTTON, self)
        self.creation_save_button.clicked.connect(self._handle_save_draft)  # type: ignore[arg-type]
        action_row.addWidget(self.creation_save_button)

        self.creation_delete_button = QPushButton(MODE1_DELETE_BUTTON, self)
        self.creation_delete_button.clicked.connect(self._handle_delete_draft)  # type: ignore[arg-type]
        action_row.addWidget(self.creation_delete_button)

        self.creation_prev_button = QPushButton(MODE1_PREV_BUTTON, self)
        self.creation_prev_button.clicked.connect(lambda: self._navigate_drafts(-1))  # type: ignore[arg-type]
        action_row.addWidget(self.creation_prev_button)

        self.creation_next_button = QPushButton(MODE1_NEXT_BUTTON, self)
        self.creation_next_button.clicked.connect(lambda: self._navigate_drafts(1))  # type: ignore[arg-type]
        action_row.addWidget(self.creation_next_button)

        self.creation_save_all_button = QPushButton(MODE1_SAVE_ALL_BUTTON, self)
        self.creation_save_all_button.clicked.connect(self._handle_save_all_drafts)  # type: ignore[arg-type]
        action_row.addWidget(self.creation_save_all_button)

        layout.addLayout(action_row)

        self.creation_question_input = QPlainTextEdit(self)
        self.creation_question_input.setPlaceholderText(PLACEHOLDER_QUESTION)
        self.creation_question_input.textChanged.connect(self._refresh_creation_preview)  # type: ignore[arg-type]
        layout.addWidget(self.creation_question_input)

        options_row = QHBoxLayout()
        self.creation_option_inputs: list[QLineEdit] = []
        for label in ("A", "B", "C", "D"):
            option_input = QLineEdit(self)
            option_input.setPlaceholderText(f"Option {label}")
            option_input.textChanged.connect(self._refresh_creation_preview)  # type: ignore[arg-type]
            options_row.addWidget(option_input)
            self.creation_option_inputs.append(option_input)
        layout.addLayout(options_row)

        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("Correct option:", self))
        self.correct_option_combo = QComboBox(self)
        self.correct_option_combo.addItem("Select…", userData=None)
        for index, label in enumerate(("A", "B", "C", "D")):
            self.correct_option_combo.addItem(label, userData=index)
        self.correct_option_combo.currentIndexChanged.connect(self._refresh_creation_preview)  # type: ignore[arg-type]
        selector_row.addWidget(self.correct_option_combo)
        layout.addLayout(selector_row)

        self.creation_preview_view = QWebEngineView(self)
        layout.addWidget(self.creation_preview_view)

        self.creation_status_label = QLabel("No draft questions yet.", self)
        layout.addWidget(self.creation_status_label)

        return panel

    def _build_mode2_import_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout()
        panel.setLayout(layout)

        instructions = QLabel(
            "Use the button below to import a quiz text file. You can return to"
            " creation mode afterwards to edit further.",
            self,
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        self.import_select_button = QPushButton(IMPORT_BUTTON_TEXT, self)
        self.import_select_button.clicked.connect(self._handle_import_quiz)  # type: ignore[arg-type]
        layout.addWidget(self.import_select_button)

        self.import_status_label = QLabel("No quiz imported yet.", self)
        self.import_status_label.setWordWrap(True)
        layout.addWidget(self.import_status_label)

        return panel

    def _build_mode3_live_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout()
        panel.setLayout(layout)

        self.live_network_label = QLabel(
            f"Students connect to: {self.student_url}", self
        )
        self.live_network_label.setWordWrap(True)
        layout.addWidget(self.live_network_label)

        self.live_toggle_button = QPushButton(MODE3_SHOW_CORRECT, self)
        self.live_toggle_button.clicked.connect(self._handle_live_toggle)  # type: ignore[arg-type]
        self.live_toggle_button.setEnabled(False)
        layout.addWidget(self.live_toggle_button)

        self.live_preview_view = QWebEngineView(self)
        layout.addWidget(self.live_preview_view)

        self.live_correct_label = QLabel("Correct answer hidden", self)
        self.live_correct_label.setAlignment(Qt.AlignCenter)
        self.live_correct_label.setVisible(False)
        layout.addWidget(self.live_correct_label)

        stats_grid = QGridLayout()
        self.option_stat_labels: list[QLabel] = []
        for idx, label in enumerate(("A", "B", "C", "D")):
            option_label = QLabel(f"{label}: 0%", self)
            self.option_stat_labels.append(option_label)
            stats_grid.addWidget(option_label, 0, idx)
        self.overall_stat_label = QLabel("Overall correctness: 0%", self)
        stats_grid.addWidget(self.overall_stat_label, 1, 0, 1, 4)
        layout.addLayout(stats_grid)

        return panel

    # ------------------------------------------------------------------
    # Timers and refresh logic
    # ------------------------------------------------------------------
    def _configure_refresh_timer(self) -> None:
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(ANSWER_REFRESH_INTERVAL_MS)
        self.refresh_timer.timeout.connect(self._refresh_state)  # type: ignore[arg-type]
        self.refresh_timer.start()

    def _refresh_state(self) -> None:
        if self._mode != TeacherMode.QUIZ_LIVE:
            return

        self._update_live_question_preview()
        self._update_live_stats()

    # ------------------------------------------------------------------
    # Mode handling
    # ------------------------------------------------------------------
    def _set_mode(self, mode: TeacherMode) -> None:
        self._mode = mode
        self.make_mode_button.setChecked(mode == TeacherMode.QUIZ_CREATION)
        self.import_mode_button.setChecked(mode == TeacherMode.QUIZ_IMPORT)
        self.start_mode_button.setChecked(mode == TeacherMode.QUIZ_LIVE)

        live_mode = mode == TeacherMode.QUIZ_LIVE
        self.make_mode_button.setEnabled(not live_mode)
        self.import_mode_button.setEnabled(not live_mode)

        self.mode_stack.setCurrentIndex(mode.value - 1)

    def _handle_start_mode_button(self) -> None:
        if self._live_session_active:
            self._stop_live_session()
            return

        self._set_mode(TeacherMode.QUIZ_LIVE)
        self._start_live_session()

    # ------------------------------------------------------------------
    # Mode 1 – quiz creation helpers
    # ------------------------------------------------------------------
    def _handle_insert_new_draft(self) -> None:
        self._current_draft_index = len(self._draft_questions)
        self._clear_creation_fields()
        self.creation_status_label.setText("Ready to insert a new question.")

    def _handle_save_draft(self) -> None:
        try:
            draft = self._build_draft_from_inputs()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid question", str(exc))
            return

        if self._current_draft_index == -1 or self._current_draft_index >= len(self._draft_questions):
            self._draft_questions.append(draft)
            self._current_draft_index = len(self._draft_questions) - 1
        else:
            self._draft_questions[self._current_draft_index] = draft

        self.creation_status_label.setText(
            f"Saved question {self._current_draft_index + 1} of {len(self._draft_questions)}."
        )

    def _handle_save_all_drafts(self) -> None:
        if not self._draft_questions:
            QMessageBox.information(self, "No drafts", "Add at least one question before saving.")
            return
        try:
            self.quiz_manager.load_quiz_from_questions(list(self._draft_questions))
        except ValueError as exc:
            QMessageBox.critical(self, "Quiz rejected", str(exc))
            return
        QMessageBox.information(self, "Quiz saved", QUIZ_SAVED_MESSAGE)

    def _handle_delete_draft(self) -> None:
        if not self._draft_questions and self._current_draft_index == -1:
            QMessageBox.information(self, "No question", "There is no saved question to delete yet.")
            return

        if self._current_draft_index == -1:
            QMessageBox.information(self, "No selection", "Select a question before deleting.")
            return

        if self._current_draft_index >= len(self._draft_questions):
            self._clear_creation_fields()
            self.creation_status_label.setText("Discarded unsaved question.")
            self._current_draft_index = -1
            return

        self._draft_questions.pop(self._current_draft_index)

        if not self._draft_questions:
            self._current_draft_index = -1
            self._clear_creation_fields()
            self.creation_status_label.setText("All draft questions removed.")
            return

        self._current_draft_index = min(self._current_draft_index, len(self._draft_questions) - 1)
        self._populate_creation_fields(self._draft_questions[self._current_draft_index])
        self.creation_status_label.setText(
            f"Deleted question. Now viewing {self._current_draft_index + 1} of {len(self._draft_questions)}."
        )

    def _navigate_drafts(self, step: int) -> None:
        if not self._draft_questions:
            return
        target = self._current_draft_index + step if self._current_draft_index != -1 else 0
        target = max(0, min(len(self._draft_questions) - 1, target))
        self._current_draft_index = target
        self._populate_creation_fields(self._draft_questions[target])
        self.creation_status_label.setText(
            f"Viewing question {target + 1} of {len(self._draft_questions)}."
        )

    def _clear_creation_fields(self) -> None:
        self.creation_question_input.clear()
        for input_field in self.creation_option_inputs:
            input_field.clear()
        self.correct_option_combo.setCurrentIndex(0)
        self._refresh_creation_preview()

    def _populate_creation_fields(self, question: QuizQuestion) -> None:
        self.creation_question_input.setPlainText(question.question_text)
        for field, text in zip(self.creation_option_inputs, question.options):
            field.setText(text)
        if question.correct_option_index is not None:
            self.correct_option_combo.setCurrentIndex(question.correct_option_index + 1)
        else:
            self.correct_option_combo.setCurrentIndex(0)
        self._refresh_creation_preview()

    def _build_draft_from_inputs(self) -> QuizQuestion:
        question_text = self.creation_question_input.toPlainText().strip()
        options = [field.text().strip() for field in self.creation_option_inputs]
        correct_data = self.correct_option_combo.currentData()
        if correct_data is None:
            raise ValueError("Select the correct option before saving.")
        return QuizQuestion(
            id=0,
            question_text=question_text,
            options=options,
            correct_option_index=int(correct_data),
        )

    def _refresh_creation_preview(self) -> None:
        question_text = self.creation_question_input.toPlainText()
        options = [field.text() for field in self.creation_option_inputs]
        html = self._render_question_with_options(question_text, options)
        if hasattr(self, "creation_preview_view"):
            self.creation_preview_view.setHtml(html)

    # ------------------------------------------------------------------
    # Mode 2 – quiz import
    # ------------------------------------------------------------------
    def _handle_import_quiz(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            IMPORT_DIALOG_TITLE,
            str(Path.home()),
            IMPORT_FILE_FILTER,
        )
        if not file_path:
            return

        try:
            imported = load_quiz_from_file(Path(file_path))
        except (OSError, QuizImportError) as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return

        try:
            self.quiz_manager.load_quiz_from_questions(imported.questions)
        except ValueError as exc:
            QMessageBox.critical(self, "Quiz rejected", str(exc))
            return

        self.import_status_label.setText(
            f"Loaded {len(imported.questions)} questions from {imported.source_path}."
        )
        QMessageBox.information(self, "Quiz imported", "Quiz is ready to run in Start mode.")

    # ------------------------------------------------------------------
    # Mode 3 – live delivery
    # ------------------------------------------------------------------
    def _start_live_session(self) -> None:
        if not self.quiz_manager.has_loaded_quiz():
            QMessageBox.warning(self, "No quiz", NO_QUIZ_LOADED_MESSAGE)
            self.start_mode_button.setChecked(False)
            self._set_mode(TeacherMode.QUIZ_CREATION)
            return

        question = self.quiz_manager.move_to_next_question()
        if question is None:
            QMessageBox.information(self, "Quiz complete", QUIZ_COMPLETE_MESSAGE)
            self.start_mode_button.setChecked(False)
            self._set_mode(TeacherMode.QUIZ_CREATION)
            return

        self._live_session_active = True
        self.start_mode_button.setText(MODE_BUTTON_STOP)
        self.live_toggle_button.setEnabled(True)
        self._live_action = LiveAction.SHOW_CORRECT
        self.live_toggle_button.setText(MODE3_SHOW_CORRECT)
        self._display_live_question(question)

    def _stop_live_session(self) -> None:
        self.quiz_manager.stop_current_question()
        self._live_session_active = False
        self.start_mode_button.setText(MODE_BUTTON_START)
        self.start_mode_button.setChecked(False)
        self.live_toggle_button.setEnabled(False)
        self.live_correct_label.setVisible(False)
        self._set_mode(TeacherMode.QUIZ_CREATION)

    def _handle_live_toggle(self) -> None:
        if not self._live_session_active:
            return
        if self._live_action == LiveAction.SHOW_CORRECT:
            self.quiz_manager.stop_current_question()
            question = self.quiz_manager.get_current_question()
            if question and question.correct_option_index is not None:
                letter = chr(ord("A") + question.correct_option_index)
                self.live_correct_label.setText(f"Correct answer: {letter}")
            else:
                self.live_correct_label.setText("Correct answer unavailable")
            self.live_correct_label.setVisible(True)
            self._live_action = LiveAction.LOAD_NEXT
            self.live_toggle_button.setText(MODE3_NEXT_QUESTION)
        else:
            question = self.quiz_manager.move_to_next_question()
            if question is None:
                QMessageBox.information(self, "Quiz complete", QUIZ_COMPLETE_MESSAGE)
                self._stop_live_session()
                return
            self.live_correct_label.setVisible(False)
            self._live_action = LiveAction.SHOW_CORRECT
            self.live_toggle_button.setText(MODE3_SHOW_CORRECT)
            self._display_live_question(question)

    def _display_live_question(self, question: QuizQuestion) -> None:
        self.live_network_label.setText(f"Students connect to: {self.student_url}")
        html = self._render_question_with_options(question.question_text, question.options)
        self.live_preview_view.setHtml(html)
        self._update_live_stats()

    def _update_live_question_preview(self) -> None:
        question = self.quiz_manager.get_current_question()
        if not question:
            return
        html = self._render_question_with_options(question.question_text, question.options)
        self.live_preview_view.setHtml(html)

    def _update_live_stats(self) -> None:
        counts = self.quiz_manager.get_option_counts()
        total = sum(counts) or 1
        for idx, label in enumerate(self.option_stat_labels):
            percentage = (counts[idx] / total) * 100
            label.setText(f"{chr(ord('A') + idx)}: {percentage:.0f}%")

        overall = self.quiz_manager.get_overall_correctness_percentage()
        self.overall_stat_label.setText(f"Overall correctness: {overall:.0f}%")

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _render_question_with_options(self, question_text: str, options: List[str]) -> str:
        markdown_lines = [question_text.strip() or "(No question text)", ""]
        for idx, option in enumerate(options):
            letter = chr(ord("A") + idx)
            markdown_lines.append(f"**{letter}.** {option or '(empty)'}")
        markdown = "\n\n".join(markdown_lines)
        return renderer.render_full_document(markdown)
