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
    QGroupBox,
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
    MODE1_SAVE_BUTTON,
    MODE3_NEXT_QUESTION,
    MODE3_SHOW_CORRECT,
    MODE_BUTTON_EDIT,
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
from quiz_app.core.models import QuizQuestion
from quiz_app.core.quiz_importer import QuizImportError, load_quiz_from_file
from quiz_app.core.quiz_manager import QuizManager
from quiz_app.ui.dialog_helpers import (
    check_unsaved_changes,
    confirm_delete_question,
    confirm_import_quiz,
    confirm_new_quiz,
    show_error,
    show_info,
    show_warning,
)
from quiz_app.ui.question_renderer import render_question_with_options
from quiz_app.ui.settings_dialog import SettingsDialog


class TeacherMode(Enum):
    """High-level UI mode for the teacher console."""

    QUIZ_CREATION = auto()
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
        self._current_question_index: int = -1
        self._has_unsaved_changes: bool = False
        self._live_session_active = False
        self._live_action = LiveAction.SHOW_CORRECT
        
        # Font size settings
        self._ui_font_size: int = 10
        self._game_font_size: int = 14
        self._show_stats_always: bool = False
        self._reset_aliases_on_new_quiz: bool = False
        self._scoreboard_size: int = 3
        self._repeat_until_all_correct: bool = False

        self._build_ui()
        self._configure_refresh_timer()
        self._refresh_creation_preview()
        self._apply_font_sizes()
        self._auto_load_default_quiz()

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
        self.mode_stack.addWidget(self._build_mode3_live_panel())
        root_layout.addWidget(self.mode_stack)

        self._set_mode(TeacherMode.QUIZ_CREATION)

    def _build_mode_buttons(self, layout: QVBoxLayout) -> None:
        button_row = QHBoxLayout()

        self.make_mode_button = QPushButton(MODE_BUTTON_MAKE, self)
        self.make_mode_button.setCheckable(True)
        self.make_mode_button.clicked.connect(self._handle_make_new_quiz)  # type: ignore[arg-type]
        button_row.addWidget(self.make_mode_button)

        self.import_mode_button = QPushButton(MODE_BUTTON_IMPORT, self)
        self.import_mode_button.clicked.connect(self._handle_import_quiz)  # type: ignore[arg-type]
        button_row.addWidget(self.import_mode_button)

        self.edit_mode_button = QPushButton(MODE_BUTTON_EDIT, self)
        self.edit_mode_button.clicked.connect(self._handle_edit_quiz)  # type: ignore[arg-type]
        button_row.addWidget(self.edit_mode_button)

        self.start_mode_button = QPushButton(MODE_BUTTON_START, self)
        self.start_mode_button.setCheckable(True)
        self.start_mode_button.clicked.connect(self._handle_start_mode_button)  # type: ignore[arg-type]
        button_row.addWidget(self.start_mode_button)
        
        self.settings_button = QPushButton("Settings", self)
        self.settings_button.clicked.connect(self._handle_settings)  # type: ignore[arg-type]
        button_row.addWidget(self.settings_button)

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

        layout.addLayout(action_row)

        self.creation_question_input = QPlainTextEdit(self)
        self.creation_question_input.setPlaceholderText(PLACEHOLDER_QUESTION)
        self.creation_question_input.textChanged.connect(self._on_input_changed)  # type: ignore[arg-type]
        layout.addWidget(self.creation_question_input)

        options_row = QHBoxLayout()
        self.creation_option_inputs: list[QLineEdit] = []
        for label in ("A", "B", "C", "D"):
            option_input = QLineEdit(self)
            option_input.setPlaceholderText(f"Option {label}")
            option_input.textChanged.connect(self._on_input_changed)  # type: ignore[arg-type]
            options_row.addWidget(option_input)
            self.creation_option_inputs.append(option_input)
        layout.addLayout(options_row)

        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("Correct option:", self))
        self.correct_option_combo = QComboBox(self)
        self.correct_option_combo.addItem("Select…", userData=None)
        for index, label in enumerate(("A", "B", "C", "D")):
            self.correct_option_combo.addItem(label, userData=index)
        self.correct_option_combo.currentIndexChanged.connect(self._on_input_changed)  # type: ignore[arg-type]
        selector_row.addWidget(self.correct_option_combo)
        layout.addLayout(selector_row)

        self.creation_preview_view = QWebEngineView(self)
        layout.addWidget(self.creation_preview_view)

        self.creation_status_label = QLabel("No draft questions yet.", self)
        layout.addWidget(self.creation_status_label)

        return panel

    def _build_mode3_live_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout()
        panel.setLayout(layout)

        # Top control row: Student URL
        control_row = QHBoxLayout()
        self.live_network_label = QLabel(f"Students connect to: {self.student_url}", self)
        self.live_network_label.setWordWrap(True)
        self.live_network_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        control_row.addWidget(self.live_network_label)
        layout.addLayout(control_row)

        # Second control row: Correct answer label and Show Correct button
        button_row = QHBoxLayout()
        self.live_correct_label = QLabel("Correct answer hidden", self)
        self.live_correct_label.setAlignment(Qt.AlignCenter)
        self.live_correct_label.setVisible(False)
        button_row.addWidget(self.live_correct_label)
        
        button_row.addStretch()  # Push button to the right
        
        self.live_toggle_button = QPushButton(MODE3_SHOW_CORRECT, self)
        self.live_toggle_button.clicked.connect(self._handle_live_toggle)  # type: ignore[arg-type]
        self.live_toggle_button.setEnabled(False)
        button_row.addWidget(self.live_toggle_button)
        
        layout.addLayout(button_row)

        # Preview and scoreboard side by side
        preview_row = QHBoxLayout()
        self.live_preview_view = QWebEngineView(self)
        preview_row.addWidget(self.live_preview_view, stretch=3)

        self.scoreboard_group = QGroupBox(self)
        self.scoreboard_group.setMinimumWidth(240)
        self.scoreboard_layout = QVBoxLayout()
        self.scoreboard_group.setLayout(self.scoreboard_layout)
        preview_row.addWidget(self.scoreboard_group, stretch=1)

        layout.addLayout(preview_row, stretch=1)

        self.scoreboard_labels: list[QLabel] = []
        self._rebuild_scoreboard_labels()

        # Stats at the bottom as a single row
        stats_row = QHBoxLayout()
        self.option_stat_labels: list[QLabel] = []
        for idx, label in enumerate(("A", "B", "C", "D")):
            option_label = QLabel(f"{label}: 0%", self)
            option_label.setVisible(False)  # Hidden by default, shown after showing correct answer
            self.option_stat_labels.append(option_label)
            stats_row.addWidget(option_label)
        
        stats_row.addStretch()
        
        self.overall_stat_label = QLabel("Overall correctness: 0%", self)
        self.overall_stat_label.setVisible(False)  # Hidden by default, shown after showing correct answer
        stats_row.addWidget(self.overall_stat_label)
        
        layout.addLayout(stats_row)

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

        # Only update stats - don't refresh the question preview to avoid flickering
        self._update_live_stats()

    # ------------------------------------------------------------------
    # Mode handling
    # ------------------------------------------------------------------
    def _set_mode(self, mode: TeacherMode) -> None:
        self._mode = mode
        self.make_mode_button.setChecked(mode == TeacherMode.QUIZ_CREATION)
        self.start_mode_button.setChecked(mode == TeacherMode.QUIZ_LIVE)

        live_mode = mode == TeacherMode.QUIZ_LIVE
        self.make_mode_button.setEnabled(not live_mode)
        self.import_mode_button.setEnabled(not live_mode)
        self.edit_mode_button.setEnabled(not live_mode)

        # Map mode to stack index (0=creation, 1=live)
        stack_index = 0 if mode == TeacherMode.QUIZ_CREATION else 1
        self.mode_stack.setCurrentIndex(stack_index)

    def _handle_make_new_quiz(self) -> None:
        """Handle Make New Quiz button with safety checks for existing quiz data.
        
        Architecture note:
        We check for unsaved changes at two levels:
        1. UI level: Draft questions that haven't been loaded to QuizManager
        2. QuizManager level: Whether a quiz is currently loaded
        
        The is_saved flag on individual questions tracks whether they've been saved
        to the draft list. But the real 'unsaved quiz' concern is whether draft
        questions exist that haven't been loaded to QuizManager yet.
        """
        # Check for unsaved changes in current draft first
        if self._has_unsaved_changes:
            if not self._check_unsaved_changes():
                return  # User cancelled
        
        # If no quiz is loaded, proceed immediately
        if not self.quiz_manager.has_loaded_quiz():
            self._reset_creation_mode()
            self._set_mode(TeacherMode.QUIZ_CREATION)
            return
        
        # A quiz exists - show warning
        if self.quiz_manager.has_loaded_quiz():
            if confirm_new_quiz(self):
                self._reset_creation_mode()
                self.quiz_manager.reset_quiz()
                self._set_mode(TeacherMode.QUIZ_CREATION)
        else:
            # No quiz loaded and no drafts (shouldn't reach here due to earlier check)
            self._reset_creation_mode()
            self._set_mode(TeacherMode.QUIZ_CREATION)

    def _reset_creation_mode(self) -> None:
        """Reset all creation mode state for a fresh start."""
        self._current_question_index = -1
        self._has_unsaved_changes = False
        self._clear_creation_fields()
        self.creation_status_label.setText("Ready to create a new quiz.")

    def _handle_edit_quiz(self) -> None:
        """Load the imported quiz questions into creation mode for editing."""
        if not self.quiz_manager.has_loaded_quiz():
            show_warning(self, "No quiz loaded", "Import a quiz first before editing.")
            return
        
        if not self._check_unsaved_changes():
            return
        
        # Start editing the loaded quiz
        if self.quiz_manager.get_question_count() > 0:
            self._current_question_index = 0
            question = self.quiz_manager.get_question_at_index(0)
            self._populate_creation_fields(question)
            self.creation_status_label.setText(
                f"Editing imported quiz. Question 1 of {self.quiz_manager.get_question_count()}."
            )
        
        self._set_mode(TeacherMode.QUIZ_CREATION)

    def _handle_start_mode_button(self) -> None:
        if self._live_session_active:
            self._stop_live_session()
            return

        self._set_mode(TeacherMode.QUIZ_LIVE)
        self._start_live_session()

    # ------------------------------------------------------------------
    # Mode 1 – quiz creation helpers
    # ------------------------------------------------------------------
    def _on_input_changed(self) -> None:
        """Mark current question as having unsaved changes and refresh preview."""
        self._has_unsaved_changes = True
        self._refresh_creation_preview()

    def _handle_insert_new_draft(self) -> None:
        if not self._check_unsaved_changes():
            return
        self._current_question_index = self.quiz_manager.get_question_count()
        self._clear_creation_fields()
        self._has_unsaved_changes = False
        self.creation_status_label.setText("Ready to insert a new question.")

    def _handle_save_draft(self) -> None:
        try:
            draft = self._build_draft_from_inputs()
        except ValueError as exc:
            show_warning(self, "Invalid question", str(exc))
            return

        try:
            if self._current_question_index == -1 or self._current_question_index >= self.quiz_manager.get_question_count():
                # Adding new question
                self.quiz_manager.add_question(draft)
                self._current_question_index = self.quiz_manager.get_question_count() - 1
            else:
                # Updating existing question
                self.quiz_manager.update_question(self._current_question_index, draft)
        except (ValueError, IndexError) as exc:
            show_error(self, "Save failed", f"Could not save question: {exc}")
            return

        self._has_unsaved_changes = False
        self.creation_status_label.setText(
            f"Saved question {self._current_question_index + 1} of {self.quiz_manager.get_question_count()}."
        )

    def _handle_delete_draft(self) -> None:
        if not self.quiz_manager.has_loaded_quiz() and self._current_question_index == -1:
            show_info(self, "No question", "There is no saved question to delete yet.")
            return

        if self._current_question_index == -1:
            show_info(self, "No selection", "Select a question before deleting.")
            return

        if self._current_question_index >= self.quiz_manager.get_question_count():
            self._clear_creation_fields()
            self._has_unsaved_changes = False
            self.creation_status_label.setText("Discarded unsaved question.")
            self._current_question_index = -1
            return

        # Show confirmation dialog
        if not confirm_delete_question(self, self._current_question_index + 1):
            return

        try:
            self.quiz_manager.delete_question(self._current_question_index)
        except IndexError as exc:
            show_error(self, "Delete failed", f"Could not delete question: {exc}")
            return

        if self.quiz_manager.get_question_count() == 0:
            self._current_question_index = -1
            self._clear_creation_fields()
            self._has_unsaved_changes = False
            self.creation_status_label.setText("All questions removed.")
            return

        self._current_question_index = min(self._current_question_index, self.quiz_manager.get_question_count() - 1)
        question = self.quiz_manager.get_question_at_index(self._current_question_index)
        self._populate_creation_fields(question)
        self._has_unsaved_changes = False
        self.creation_status_label.setText(
            f"Deleted question. Now viewing {self._current_question_index + 1} of {self.quiz_manager.get_question_count()}."
        )

    def _navigate_drafts(self, step: int) -> None:
        if not self._check_unsaved_changes():
            return
        if not self.quiz_manager.has_loaded_quiz():
            return
        target = self._current_question_index + step if self._current_question_index != -1 else 0
        target = max(0, min(self.quiz_manager.get_question_count() - 1, target))
        self._current_question_index = target
        question = self.quiz_manager.get_question_at_index(target)
        self._populate_creation_fields(question)
        self._has_unsaved_changes = False
        self.creation_status_label.setText(
            f"Viewing question {target + 1} of {self.quiz_manager.get_question_count()}."
        )

    def _check_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes and prompt user. Returns True if ok to proceed."""
        if not self._has_unsaved_changes:
            return True
        
        result = check_unsaved_changes(self)
        
        if result is True:  # Save
            self._handle_save_draft()
            return not self._has_unsaved_changes  # Only proceed if save was successful
        elif result is False:  # Discard
            self._has_unsaved_changes = False
            return True
        else:  # Cancel (None)
            return False

    def _clear_creation_fields(self) -> None:
        self.creation_question_input.clear()
        for input_field in self.creation_option_inputs:
            input_field.clear()
        self.correct_option_combo.setCurrentIndex(0)
        self._has_unsaved_changes = False
        self._refresh_creation_preview()

    def _populate_creation_fields(self, question: QuizQuestion) -> None:
        self.creation_question_input.setPlainText(question.question_text)
        for field, text in zip(self.creation_option_inputs, question.options):
            field.setText(text)
        if question.correct_option_index is not None:
            self.correct_option_combo.setCurrentIndex(question.correct_option_index + 1)
        else:
            self.correct_option_combo.setCurrentIndex(0)
        self._has_unsaved_changes = False
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
            is_saved=True,
        )

    def _refresh_creation_preview(self) -> None:
        question_text = self.creation_question_input.toPlainText()
        options = [field.text() for field in self.creation_option_inputs]
        html = render_question_with_options(question_text, options)
        if hasattr(self, "creation_preview_view"):
            self.creation_preview_view.setHtml(html)

    # ------------------------------------------------------------------
    # Mode 2 – quiz import
    # ------------------------------------------------------------------
    def _handle_import_quiz(self) -> None:
        """Import a quiz from a file with unsaved changes check."""
        # Check for unsaved changes in current question
        if self._has_unsaved_changes:
            if not self._check_unsaved_changes():
                return  # User cancelled
        
        # Warn if a quiz is already loaded
        if self.quiz_manager.has_loaded_quiz():
            if not confirm_import_quiz(self):
                return
        
        # Open file dialog
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
            show_error(self, "Import failed", str(exc))
            return

        try:
            self.quiz_manager.load_quiz_from_questions(imported.questions)
        except ValueError as exc:
            show_error(self, "Quiz rejected", str(exc))
            return

        # Load and display the first question
        self._current_question_index = 0
        self._has_unsaved_changes = False
        question = self.quiz_manager.get_question_at_index(0)
        self._populate_creation_fields(question)
        
        # Switch to creation mode to show the questions
        self._set_mode(TeacherMode.QUIZ_CREATION)
        
        self.creation_status_label.setText(
            f"Imported {len(imported.questions)} questions. Viewing question 1 of {len(imported.questions)}."
        )
        
        show_info(
            self, 
            "Quiz imported", 
            f"Successfully imported {len(imported.questions)} questions. You can now edit or start the quiz."
        )

    # ------------------------------------------------------------------
    # Mode 3 – live delivery
    # ------------------------------------------------------------------
    def _start_live_session(self) -> None:
        if not self.quiz_manager.has_loaded_quiz():
            show_warning(self, "No quiz", NO_QUIZ_LOADED_MESSAGE)
            self.start_mode_button.setChecked(False)
            self._set_mode(TeacherMode.QUIZ_CREATION)
            return

        if self._reset_aliases_on_new_quiz:
            self.quiz_manager.reset_student_aliases()
            self._update_scoreboard_view()

        question = self.quiz_manager.move_to_next_question()
        if question is None:
            show_info(self, "Quiz complete", QUIZ_COMPLETE_MESSAGE)
            self.start_mode_button.setChecked(False)
            self._update_questions_remaining_label()
            self._set_mode(TeacherMode.QUIZ_CREATION)
            return

        self._live_session_active = True
        self.start_mode_button.setText(MODE_BUTTON_STOP)
        self.live_toggle_button.setEnabled(True)
        self._live_action = LiveAction.SHOW_CORRECT
        self._update_next_question_button_label()
        self._hide_stats()  # Hide all stats when starting question
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
            self._show_stats()  # Show all stats after showing correct answer
            self._live_action = LiveAction.LOAD_NEXT
            self._update_next_question_button_label()
        else:
            question = self.quiz_manager.move_to_next_question()
            if question is None:
                show_info(self, "Quiz complete", QUIZ_COMPLETE_MESSAGE)
                self._stop_live_session()
                return
            self.live_correct_label.setVisible(False)
            self._hide_stats()  # Hide all stats when loading next question
            self._live_action = LiveAction.SHOW_CORRECT
            self._update_next_question_button_label()
            self._display_live_question(question)

    def _display_live_question(self, question: QuizQuestion) -> None:
        self.live_network_label.setText(f"Students connect to: {self.student_url}")
        html = render_question_with_options(question.question_text, question.options, self._game_font_size)
        self.live_preview_view.setHtml(html)
        self._update_live_stats()
        self._update_scoreboard_view()

    def _update_live_question_preview(self) -> None:
        question = self.quiz_manager.get_current_question()
        if not question:
            return
        html = render_question_with_options(question.question_text, question.options)
        self.live_preview_view.setHtml(html)

    def _update_live_stats(self) -> None:
        counts = self.quiz_manager.get_option_counts()
        total = sum(counts) or 1
        for idx, label in enumerate(self.option_stat_labels):
            percentage = (counts[idx] / total) * 100
            label.setText(f"{chr(ord('A') + idx)}: {percentage:.0f}%")

        overall = self.quiz_manager.get_overall_correctness_percentage()
        self.overall_stat_label.setText(f"Overall correctness: {overall:.0f}%")
        self._update_scoreboard_view()

    def _rebuild_scoreboard_labels(self) -> None:
        if not hasattr(self, "scoreboard_layout"):
            return

        while self.scoreboard_layout.count():
            item = self.scoreboard_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.scoreboard_labels = []
        for idx in range(self._scoreboard_size):
            label = QLabel(f"{idx + 1}. —", self)
            label.setAlignment(Qt.AlignLeft)
            self.scoreboard_layout.addWidget(label)
            self.scoreboard_labels.append(label)

        self.scoreboard_layout.addStretch()
        self._update_scoreboard_group_title()
        self._update_scoreboard_label_styles()

    def _update_scoreboard_view(self) -> None:
        if not hasattr(self, "scoreboard_labels") or not self.scoreboard_labels:
            return
        entries = self.quiz_manager.get_top_scorers(self._scoreboard_size)
        for idx, label in enumerate(self.scoreboard_labels):
            if idx < len(entries):
                entry = entries[idx]
                label.setText(f"{idx + 1}. {entry.display_name}")
            else:
                label.setText(f"{idx + 1}. —")

    def _update_scoreboard_group_title(self) -> None:
        if hasattr(self, "scoreboard_group"):
            self.scoreboard_group.setTitle(f"Top {self._scoreboard_size}") # Top N Students

    def _update_scoreboard_label_styles(self) -> None:
        if not hasattr(self, "scoreboard_labels"):
            return
        label_style = f"font-size: {self._game_font_size}pt;"
        for label in self.scoreboard_labels:
            label.setStyleSheet(label_style)

    # ------------------------------------------------------------------
    # Auto-load default quiz
    # ------------------------------------------------------------------
    def _auto_load_default_quiz(self) -> None:
        """Automatically load quiz_questions.txt if it exists in the current directory."""
        default_quiz_path = Path("quiz_questions.txt")
        if not default_quiz_path.exists():
            return
        
        try:
            imported = load_quiz_from_file(default_quiz_path)
            self.quiz_manager.load_quiz_from_questions(imported.questions)
            
            # Load and display the first question
            self._current_question_index = 0
            self._has_unsaved_changes = False
            question = self.quiz_manager.get_question_at_index(0)
            self._populate_creation_fields(question)
            
            self.creation_status_label.setText(
                f"Auto-loaded quiz_questions.txt: {len(imported.questions)} questions. Viewing question 1."
            )
        except (OSError, QuizImportError, ValueError):
            # Silently fail - don't interrupt startup if default quiz can't load
            pass

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def _handle_settings(self) -> None:
        """Open settings dialog and apply changes."""
        dialog = SettingsDialog(
            self,
            self._ui_font_size,
            self._game_font_size,
            self._show_stats_always,
            self._reset_aliases_on_new_quiz,
            self._scoreboard_size,
            self._repeat_until_all_correct,
        )
        if dialog.exec():
            self._ui_font_size = dialog.get_ui_font_size()
            self._game_font_size = dialog.get_game_font_size()
            self._show_stats_always = dialog.get_show_stats_always()
            self._reset_aliases_on_new_quiz = dialog.get_reset_aliases_on_start()
            self._scoreboard_size = dialog.get_scoreboard_size()
            self._repeat_until_all_correct = dialog.get_repeat_until_all_correct()
            self.quiz_manager.set_repeat_until_all_correct(self._repeat_until_all_correct)
            self._apply_font_sizes()
            self._rebuild_scoreboard_labels()
            self._update_scoreboard_view()
            
            # Apply stats visibility if in live mode
            if self._mode == TeacherMode.QUIZ_LIVE and self._live_session_active:
                if self._show_stats_always:
                    self._show_stats()
                elif self._live_action == LiveAction.LOAD_NEXT:
                    # Stats should be visible (answer already shown)
                    self._show_stats()
                else:
                    # Question is active, hide stats
                    self._hide_stats()
    
    def _show_stats(self) -> None:
        """Show all statistics labels."""
        for label in self.option_stat_labels:
            label.setVisible(True)
        self.overall_stat_label.setVisible(True)
    
    def _hide_stats(self) -> None:
        """Hide all statistics labels (unless show_stats_always is enabled)."""
        if self._show_stats_always:
            return  # Keep stats visible when in always-show mode
        
        for label in self.option_stat_labels:
            label.setVisible(False)
        self.overall_stat_label.setVisible(False)
    
    def _apply_font_sizes(self) -> None:
        """Apply font sizes to UI elements."""
        # Apply UI font size to buttons and controls
        ui_style = f"font-size: {self._ui_font_size}pt;"
        for button in [
            self.make_mode_button,
            self.import_mode_button,
            self.edit_mode_button,
            self.start_mode_button,
            self.settings_button,
            self.creation_insert_button,
            self.creation_save_button,
            self.creation_delete_button,
            self.creation_prev_button,
            self.creation_next_button,
        ]:
            button.setStyleSheet(ui_style)
        
        # Apply game font size to live mode elements
        self.live_network_label.setStyleSheet(
            f"font-size: {self._game_font_size}pt; font-weight: bold;"
        )
        
        game_label_style = f"font-size: {self._game_font_size}pt;"
        self.live_correct_label.setStyleSheet(game_label_style)
        self.live_toggle_button.setStyleSheet(game_label_style)
        
        # Apply to stats labels
        for label in self.option_stat_labels:
            label.setStyleSheet(game_label_style)
        self.overall_stat_label.setStyleSheet(game_label_style)
        self._update_scoreboard_label_styles()
        
        # Refresh live preview if in live mode with a question displayed
        if self._mode == TeacherMode.QUIZ_LIVE and self._live_session_active:
            question = self.quiz_manager.get_current_question()
            if question:
                html = render_question_with_options(question.question_text, question.options, self._game_font_size)
                self.live_preview_view.setHtml(html)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _update_next_question_button_label(self) -> None:
        if not hasattr(self, "live_toggle_button"):
            return
        if self._live_action == LiveAction.LOAD_NEXT:
            remaining = self.quiz_manager.get_remaining_question_count()
            self.live_toggle_button.setText(f"{MODE3_NEXT_QUESTION} ({remaining} Q left)")
        else:
            self.live_toggle_button.setText(MODE3_SHOW_CORRECT)
