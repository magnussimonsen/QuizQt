"""Qt main window implementing creation/import/live quiz modes."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from quiz_app.constants.about import (
    APP_ABOUT_TEXT,
    APP_AUTHOR,
    APP_AI,
    HELP_TEXT,
    APP_LICENSE,
    APP_NAME,
    APP_REPOSITORY_URL,
    APP_VERSION,
)
from quiz_app.constants.ui_constants import (
    ANSWER_REFRESH_INTERVAL_MS,
    EXPORT_DIALOG_TITLE,
    EXPORT_FILE_FILTER,
    IMPORT_DIALOG_TITLE,
    IMPORT_FILE_FILTER,
    MODE_BUTTON_IMPORT,
    MODE_BUTTON_SAVE_FILE,
    MODE_BUTTON_MAKE,
    MODE_BUTTON_START,
    MODE_BUTTON_STOP,
    NO_QUIZ_LOADED_MESSAGE,
    STUDENT_URL_PLACEHOLDER,
    WINDOW_TITLE,
)
from quiz_app.core.quiz_exporter import save_quiz_to_file
from quiz_app.core.quiz_importer import QuizImportError, load_quiz_from_file
from quiz_app.core.quiz_manager import QuizManager
from quiz_app.ui.dialog_helpers import (
    confirm_import_quiz,
    confirm_new_quiz,
    show_error,
    show_info,
    show_warning,
)
from quiz_app.ui.settings_dialog import SettingsDialog
from quiz_app.ui.components.creation_panel import CreationPanel
from quiz_app.ui.components.lobby_panel import LobbyPanel
from quiz_app.ui.components.live_panel import LivePanel
from quiz_app.styling.styles import Styles
from enum import Enum, auto

class TeacherMode(Enum):
    """High-level UI mode for the teacher console."""

    QUIZ_CREATION = auto()
    QUIZ_LOBBY = auto()
    QUIZ_LIVE = auto()


class TeacherMainWindow(QMainWindow):
    """Main Qt window orchestrating the three application modes."""

    def __init__(self, quiz_manager: QuizManager, student_url: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)

        self.quiz_manager = quiz_manager
        self.student_url = student_url or STUDENT_URL_PLACEHOLDER

        self._mode = TeacherMode.QUIZ_CREATION
        self._live_session_active = False
        self._lobby_session_open = False
        
        # Font size settings
        self._ui_font_size: int = 10
        self._game_font_size: int = 14
        self._show_stats_always: bool = False
        self._reset_aliases_on_new_quiz: bool = False
        self._scoreboard_size: int = 3
        self._repeat_until_all_correct: bool = False
        self._shuffle_seed: int | None = None
        self._last_export_path: Path | None = None

        self._build_ui()
        self._configure_refresh_timer()
        self._apply_styles()
        self.quiz_manager.set_shuffle_seed(self._shuffle_seed)
        self._auto_load_default_quiz()

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout()
        central_widget.setLayout(root_layout)

        self._build_mode_buttons(root_layout)

        self.mode_stack = QStackedWidget(self)
        
        # Initialize components
        self.creation_panel = CreationPanel(self.quiz_manager, self)
        self.lobby_panel = LobbyPanel(
            self.quiz_manager, 
            self.student_url, 
            on_start_quiz=self._handle_begin_quiz_from_lobby,
            on_cancel=self._cancel_lobby_session,
            parent=self
        )
        self.live_panel = LivePanel(
            self.quiz_manager, 
            self.student_url, 
            on_stop_session=self._stop_live_session,
            parent=self
        )

        self.mode_stack.addWidget(self.creation_panel)
        self.mode_stack.addWidget(self.lobby_panel)
        self.mode_stack.addWidget(self.live_panel)
        
        root_layout.addWidget(self.mode_stack)

        self._set_mode(TeacherMode.QUIZ_CREATION)

    def _build_mode_buttons(self, layout: QVBoxLayout) -> None:
        button_row = QHBoxLayout()

        self.make_mode_button = QPushButton(MODE_BUTTON_MAKE, self)
        self.make_mode_button.setCheckable(True)
        self.make_mode_button.clicked.connect(self._handle_make_new_quiz)
        button_row.addWidget(self.make_mode_button)

        self.save_quiz_button = QPushButton(MODE_BUTTON_SAVE_FILE, self)
        self.save_quiz_button.clicked.connect(self._handle_save_quiz_to_file)
        button_row.addWidget(self.save_quiz_button)

        self.import_mode_button = QPushButton(MODE_BUTTON_IMPORT, self)
        self.import_mode_button.clicked.connect(self._handle_import_quiz)
        button_row.addWidget(self.import_mode_button)

        self.start_mode_button = QPushButton(MODE_BUTTON_START, self)
        self.start_mode_button.setCheckable(True)
        self.start_mode_button.clicked.connect(self._handle_start_mode_button)
        button_row.addWidget(self.start_mode_button)
        
        self.about_button = QPushButton("About QuizQt", self)
        self.about_button.clicked.connect(self._handle_about)
        button_row.addWidget(self.about_button)

        self.help_button = QPushButton("Help", self)
        self.help_button.clicked.connect(self._handle_help)
        button_row.addWidget(self.help_button)

        self.settings_button = QPushButton("Settings", self)
        self.settings_button.clicked.connect(self._handle_settings)
        button_row.addWidget(self.settings_button)

        layout.addLayout(button_row)

    def _configure_refresh_timer(self) -> None:
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(ANSWER_REFRESH_INTERVAL_MS)
        self.refresh_timer.timeout.connect(self._refresh_state)
        self.refresh_timer.start()

    def _refresh_state(self) -> None:
        if self._mode == TeacherMode.QUIZ_LIVE:
            self.live_panel.update_stats()
        elif self._mode == TeacherMode.QUIZ_LOBBY:
            self.lobby_panel.refresh_participants()

    def _set_mode(self, mode: TeacherMode) -> None:
        self._mode = mode
        self.make_mode_button.setChecked(mode == TeacherMode.QUIZ_CREATION)
        self.start_mode_button.setChecked(mode in (TeacherMode.QUIZ_LOBBY, TeacherMode.QUIZ_LIVE))

        live_mode = mode == TeacherMode.QUIZ_LIVE
        lobby_mode = mode == TeacherMode.QUIZ_LOBBY
        disable_main_modes = live_mode or lobby_mode
        self.make_mode_button.setEnabled(not disable_main_modes)
        self.import_mode_button.setEnabled(not disable_main_modes)
        self.save_quiz_button.setEnabled(not disable_main_modes)

        index_map = {
            TeacherMode.QUIZ_CREATION: 0,
            TeacherMode.QUIZ_LOBBY: 1,
            TeacherMode.QUIZ_LIVE: 2,
        }
        self.mode_stack.setCurrentIndex(index_map[mode])

    def _handle_make_new_quiz(self) -> None:
        if not self.creation_panel.check_unsaved_changes():
            return
        
        if not self.quiz_manager.has_loaded_quiz():
            self.creation_panel.reset_state()
            self._set_mode(TeacherMode.QUIZ_CREATION)
            return
        
        if self.quiz_manager.has_loaded_quiz():
            if confirm_new_quiz(self):
                self.creation_panel.reset_state()
                self.quiz_manager.reset_quiz()
                self._set_mode(TeacherMode.QUIZ_CREATION)

    def _handle_start_mode_button(self) -> None:
        if self._live_session_active:
            self._stop_live_session()
            return

        if self._lobby_session_open:
            self._cancel_lobby_session()
            return

        self._enter_lobby_mode()

    def _enter_lobby_mode(self) -> None:
        if not self.quiz_manager.has_loaded_quiz():
            show_warning(self, "No quiz", NO_QUIZ_LOADED_MESSAGE)
            self.start_mode_button.setChecked(False)
            return

        if self._reset_aliases_on_new_quiz:
             self.quiz_manager.reset_student_aliases()

        self.quiz_manager.begin_lobby_session()
        self._lobby_session_open = True
        self.start_mode_button.setText(MODE_BUTTON_STOP)
        self.start_mode_button.setChecked(True)
        
        self.lobby_panel.reset_state()
        self.lobby_panel.update_student_url(self.student_url)
        self._set_mode(TeacherMode.QUIZ_LOBBY)
        self.lobby_panel.refresh_participants()

    def _cancel_lobby_session(self) -> None:
        self.quiz_manager.cancel_lobby_session()
        self._lobby_session_open = False
        self.start_mode_button.setText(MODE_BUTTON_START)
        self.start_mode_button.setChecked(False)
        self.start_mode_button.setEnabled(True)
        self._set_mode(TeacherMode.QUIZ_CREATION)

    def _handle_begin_quiz_from_lobby(self) -> None:
        if not self._lobby_session_open:
            return
        success = self._start_live_session()
        if success:
            self.quiz_manager.finalize_lobby_students()
            self._lobby_session_open = False
        else:
            self._cancel_lobby_session()

    def _start_live_session(self) -> bool:
        if not self.quiz_manager.has_loaded_quiz():
            show_warning(self, "No quiz", NO_QUIZ_LOADED_MESSAGE)
            self.start_mode_button.setChecked(False)
            self._set_mode(TeacherMode.QUIZ_CREATION)
            return False

        if not self.live_panel.start_session():
            self.start_mode_button.setChecked(False)
            self._set_mode(TeacherMode.QUIZ_CREATION)
            return False

        self._live_session_active = True
        self.start_mode_button.setText(MODE_BUTTON_STOP)
        self.start_mode_button.setEnabled(True)
        self._set_mode(TeacherMode.QUIZ_LIVE)
        self._lobby_session_open = False
        return True

    def _stop_live_session(self) -> None:
        self.live_panel.stop_session()
        self._live_session_active = False
        self.start_mode_button.setText(MODE_BUTTON_START)
        self.start_mode_button.setChecked(False)
        self.start_mode_button.setEnabled(True)
        self._set_mode(TeacherMode.QUIZ_CREATION)

    def _handle_import_quiz(self) -> None:
        if not self.creation_panel.check_unsaved_changes():
            return
        
        if self.quiz_manager.has_loaded_quiz():
            if not confirm_import_quiz(self):
                return
        
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

        self.creation_panel.set_current_index(0)
        question = self.quiz_manager.get_question_at_index(0)
        self.creation_panel.populate_fields(question)
        
        self._set_mode(TeacherMode.QUIZ_CREATION)
        
        self.creation_panel.set_status_message(
            f"Imported {len(imported.questions)} questions. Viewing question 1 of {len(imported.questions)}."
        )
        
        show_info(
            self, 
            "Quiz imported", 
            f"Successfully imported {len(imported.questions)} questions. You can now edit or start the quiz."
        )

    def _handle_save_quiz_to_file(self) -> None:
        if not self.quiz_manager.has_loaded_quiz():
            show_warning(self, "No quiz", NO_QUIZ_LOADED_MESSAGE)
            return

        if not self.creation_panel.check_unsaved_changes():
            return

        default_path = self._last_export_path or (Path.cwd() / "quiz_export.txt")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            EXPORT_DIALOG_TITLE,
            str(default_path),
            EXPORT_FILE_FILTER,
        )
        if not file_path:
            return

        try:
            save_quiz_to_file(Path(file_path), self.quiz_manager.get_loaded_questions())
        except (OSError, ValueError) as exc:
            show_error(self, "Export failed", str(exc))
            return

        self._last_export_path = Path(file_path)
        show_info(self, "Quiz saved", f"Quiz exported to {file_path}.")

    def _auto_load_default_quiz(self) -> None:
        default_quiz_path = Path("quiz_questions.txt")
        if not default_quiz_path.exists():
            return
        
        try:
            imported = load_quiz_from_file(default_quiz_path)
            self.quiz_manager.load_quiz_from_questions(imported.questions)
            
            self.creation_panel.set_current_index(0)
            question = self.quiz_manager.get_question_at_index(0)
            self.creation_panel.populate_fields(question)
            
            self.creation_panel.set_status_message(
                f"Auto-loaded quiz_questions.txt: {len(imported.questions)} questions. Viewing question 1."
            )
        except (OSError, QuizImportError, ValueError):
            pass

    def _handle_about(self) -> None:
        details = (
            f"{APP_NAME} v{APP_VERSION}\n"
            f"Author: {APP_AUTHOR}\n"
            f"AI Assistant: {APP_AI}\n"
            f"License: {APP_LICENSE}\n\n"
            f"{APP_ABOUT_TEXT}\n\n"
            f"Repository: {APP_REPOSITORY_URL}"
        )
        show_info(self, f"About {APP_NAME}", details)

    def _handle_help(self) -> None:
        show_info(self, "QuizQt Help", HELP_TEXT)
    def _handle_settings(self) -> None:
        dialog = SettingsDialog(
            self,
            self._ui_font_size,
            self._game_font_size,
            self._show_stats_always,
            self._reset_aliases_on_new_quiz,
            self._scoreboard_size,
            self._repeat_until_all_correct,
            self._shuffle_seed,
        )
        if dialog.exec():
            self._ui_font_size = dialog.get_ui_font_size()
            self._game_font_size = dialog.get_game_font_size()
            self._show_stats_always = dialog.get_show_stats_always()
            self._reset_aliases_on_new_quiz = dialog.get_reset_aliases_on_start()
            self._scoreboard_size = dialog.get_scoreboard_size()
            self._repeat_until_all_correct = dialog.get_repeat_until_all_correct()
            self._shuffle_seed = dialog.get_shuffle_seed()
            
            self.quiz_manager.set_repeat_until_all_correct(self._repeat_until_all_correct)
            self.quiz_manager.set_shuffle_seed(self._shuffle_seed)
            
            self._apply_styles()

    def _apply_styles(self) -> None:
        self.setStyleSheet(Styles.get_main_window_style())
        
        # Apply UI font size to main buttons
        ui_style = f"font-size: {self._ui_font_size}pt;"
        buttons = [
            self.make_mode_button,
            self.import_mode_button,
            self.save_quiz_button,
            self.start_mode_button,
            self.about_button,
            self.settings_button,
        ]
        for button in buttons:
            button.setStyleSheet(ui_style)

        # Pass settings to components
        self.creation_panel.apply_font_size(self._ui_font_size)
        self.lobby_panel.apply_font_size(self._game_font_size)
        self.live_panel.set_game_font_size(self._game_font_size)
        self.live_panel.set_scoreboard_size(self._scoreboard_size)
        self.live_panel.set_show_stats_always(self._show_stats_always)
