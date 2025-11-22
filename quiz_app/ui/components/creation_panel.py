"""Component for creating and editing quiz questions."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from quiz_app.constants.ui_constants import (
    MODE1_DELETE_BUTTON,
    MODE1_INSERT_BUTTON,
    MODE1_NEXT_BUTTON,
    MODE1_PREV_BUTTON,
    MODE1_SAVE_BUTTON,
    PLACEHOLDER_QUESTION,
)
from quiz_app.constants.quiz_constants import DEFAULT_TIME_LIMIT_SECONDS
from quiz_app.core.models import QuizQuestion
from quiz_app.core.quiz_manager import QuizManager
from quiz_app.ui.dialog_helpers import (
    check_unsaved_changes,
    confirm_delete_question,
    show_error,
    show_info,
    show_warning,
)
from quiz_app.ui.question_renderer import render_question_with_options
from quiz_app.styling.styles import Styles


class CreationPanel(QWidget):
    """UI component for creating, editing, and navigating quiz questions."""

    def __init__(self, quiz_manager: QuizManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.quiz_manager = quiz_manager
        self._current_question_index: int = -1
        self._has_unsaved_changes: bool = False
        
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Action buttons
        action_row = QHBoxLayout()
        self.insert_button = QPushButton(MODE1_INSERT_BUTTON, self)
        self.insert_button.clicked.connect(self._handle_insert_new_draft)
        action_row.addWidget(self.insert_button)

        self.save_button = QPushButton(MODE1_SAVE_BUTTON, self)
        self.save_button.clicked.connect(self._handle_save_draft)
        action_row.addWidget(self.save_button)

        self.delete_button = QPushButton(MODE1_DELETE_BUTTON, self)
        self.delete_button.clicked.connect(self._handle_delete_draft)
        action_row.addWidget(self.delete_button)

        self.prev_button = QPushButton(MODE1_PREV_BUTTON, self)
        self.prev_button.clicked.connect(lambda: self._navigate_drafts(-1))
        action_row.addWidget(self.prev_button)

        self.next_button = QPushButton(MODE1_NEXT_BUTTON, self)
        self.next_button.clicked.connect(lambda: self._navigate_drafts(1))
        action_row.addWidget(self.next_button)

        layout.addLayout(action_row)

        # Question input
        self.question_input = QPlainTextEdit(self)
        self.question_input.setPlaceholderText(PLACEHOLDER_QUESTION)
        self.question_input.textChanged.connect(self._on_input_changed)
        layout.addWidget(self.question_input)

        # Options input
        options_row = QHBoxLayout()
        self.option_inputs: list[QLineEdit] = []
        for label in ("A", "B", "C", "D"):
            option_input = QLineEdit(self)
            option_input.setPlaceholderText(f"Option {label}")
            option_input.textChanged.connect(self._on_input_changed)
            options_row.addWidget(option_input)
            self.option_inputs.append(option_input)
        layout.addLayout(options_row)

        # Time limit
        time_limit_row = QHBoxLayout()
        self.time_limit_checkbox = QCheckBox("Enable time limit for this question", self)
        self.time_limit_checkbox.toggled.connect(self._handle_time_limit_toggle)
        time_limit_row.addWidget(self.time_limit_checkbox)

        self.time_limit_spinbox = QSpinBox(self)
        self.time_limit_spinbox.setRange(5, 3600)
        self.time_limit_spinbox.setSingleStep(5)
        self.time_limit_spinbox.setSuffix(" s")
        self.time_limit_spinbox.setEnabled(False)
        self.time_limit_spinbox.setValue(DEFAULT_TIME_LIMIT_SECONDS)
        self.time_limit_spinbox.valueChanged.connect(lambda _: self._on_input_changed())
        time_limit_row.addWidget(self.time_limit_spinbox)

        layout.addLayout(time_limit_row)

        # Correct option selector
        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("Correct option:", self))
        self.correct_option_combo = QComboBox(self)
        self.correct_option_combo.addItem("Select…", userData=None)
        for index, label in enumerate(("A", "B", "C", "D")):
            self.correct_option_combo.addItem(label, userData=index)
        self.correct_option_combo.currentIndexChanged.connect(self._on_input_changed)
        selector_row.addWidget(self.correct_option_combo)
        layout.addLayout(selector_row)

        # Preview
        self.preview_view = QWebEngineView(self)
        layout.addWidget(self.preview_view)

        # Status label
        self.status_label = QLabel("No draft questions yet.", self)
        layout.addWidget(self.status_label)

    def _on_input_changed(self) -> None:
        self._has_unsaved_changes = True
        self._refresh_preview()

    def _handle_time_limit_toggle(self, checked: bool) -> None:
        self.time_limit_spinbox.setEnabled(checked)
        if checked and self.time_limit_spinbox.value() <= 0:
            self.time_limit_spinbox.setValue(DEFAULT_TIME_LIMIT_SECONDS)
        self._on_input_changed()

    def _handle_insert_new_draft(self) -> None:
        if not self.check_unsaved_changes():
            return
        self._current_question_index = self.quiz_manager.get_question_count()
        self.clear_fields()
        self._has_unsaved_changes = False
        self.status_label.setText("Ready to insert a new question.")

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
        self.status_label.setText(
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
            self.clear_fields()
            self._has_unsaved_changes = False
            self.status_label.setText("Discarded unsaved question.")
            self._current_question_index = -1
            return

        if not confirm_delete_question(self, self._current_question_index + 1):
            return

        try:
            self.quiz_manager.delete_question(self._current_question_index)
        except IndexError as exc:
            show_error(self, "Delete failed", f"Could not delete question: {exc}")
            return

        if self.quiz_manager.get_question_count() == 0:
            self._current_question_index = -1
            self.clear_fields()
            self._has_unsaved_changes = False
            self.status_label.setText("All questions removed.")
            return

        self._current_question_index = min(self._current_question_index, self.quiz_manager.get_question_count() - 1)
        question = self.quiz_manager.get_question_at_index(self._current_question_index)
        self.populate_fields(question)
        self._has_unsaved_changes = False
        self.status_label.setText(
            f"Deleted question. Now viewing {self._current_question_index + 1} of {self.quiz_manager.get_question_count()}."
        )

    def _navigate_drafts(self, step: int) -> None:
        if not self.check_unsaved_changes():
            return
        if not self.quiz_manager.has_loaded_quiz():
            return
        target = self._current_question_index + step if self._current_question_index != -1 else 0
        target = max(0, min(self.quiz_manager.get_question_count() - 1, target))
        self._current_question_index = target
        question = self.quiz_manager.get_question_at_index(target)
        self.populate_fields(question)
        self._has_unsaved_changes = False
        self.status_label.setText(
            f"Viewing question {target + 1} of {self.quiz_manager.get_question_count()}."
        )

    def check_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes and prompt user. Returns True if ok to proceed."""
        if not self._has_unsaved_changes:
            return True
        
        result = check_unsaved_changes(self)
        
        if result is True:  # Save
            self._handle_save_draft()
            return not self._has_unsaved_changes
        elif result is False:  # Discard
            self._has_unsaved_changes = False
            return True
        else:  # Cancel (None)
            return False

    def clear_fields(self) -> None:
        self.question_input.clear()
        for input_field in self.option_inputs:
            input_field.clear()
        self.correct_option_combo.setCurrentIndex(0)
        self.time_limit_checkbox.setChecked(False)
        self.time_limit_spinbox.setValue(DEFAULT_TIME_LIMIT_SECONDS)
        self._has_unsaved_changes = False
        self._refresh_preview()

    def populate_fields(self, question: QuizQuestion) -> None:
        self.question_input.setPlainText(question.question_text)
        for field, text in zip(self.option_inputs, question.options):
            field.setText(text)
        if question.correct_option_index is not None:
            self.correct_option_combo.setCurrentIndex(question.correct_option_index + 1)
        else:
            self.correct_option_combo.setCurrentIndex(0)
        
        if question.time_limit_seconds is not None:
            self.time_limit_spinbox.setValue(question.time_limit_seconds)
            self.time_limit_checkbox.setChecked(True)
        else:
            self.time_limit_spinbox.setValue(DEFAULT_TIME_LIMIT_SECONDS)
            self.time_limit_checkbox.setChecked(False)
            
        self._has_unsaved_changes = False
        self._refresh_preview()

    def _build_draft_from_inputs(self) -> QuizQuestion:
        question_text = self.question_input.toPlainText().strip()
        options = [field.text().strip() for field in self.option_inputs]
        correct_data = self.correct_option_combo.currentData()
        if correct_data is None:
            raise ValueError("Select the correct option before saving.")
        time_limit = None
        if self.time_limit_checkbox.isChecked():
            time_limit = int(self.time_limit_spinbox.value())
        return QuizQuestion(
            id=0,
            question_text=question_text,
            options=options,
            time_limit_seconds=time_limit,
            correct_option_index=int(correct_data),
            is_saved=True,
        )

    def _refresh_preview(self) -> None:
        question_text = self.question_input.toPlainText()
        options = [field.text() for field in self.option_inputs]
        html = render_question_with_options(question_text, options)
        self.preview_view.setHtml(html)

    def reset_state(self) -> None:
        """Reset the panel to its initial state."""
        self._current_question_index = -1
        self.clear_fields()
        self.status_label.setText("Ready to create a new quiz.")

    def set_status_message(self, message: str) -> None:
        self.status_label.setText(message)
    
    def set_current_index(self, index: int) -> None:
        self._current_question_index = index

    def apply_font_size(self, font_size: int) -> None:
        style = f"font-size: {font_size}pt;"
        buttons = [
            self.insert_button,
            self.save_button,
            self.delete_button,
            self.prev_button,
            self.next_button,
        ]
        for button in buttons:
            button.setStyleSheet(style)
