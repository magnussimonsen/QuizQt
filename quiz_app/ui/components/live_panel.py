"""Component for the live quiz delivery interface."""

from __future__ import annotations

from datetime import datetime, timedelta
import math
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from quiz_app.constants.ui_constants import (
    MODE3_NEXT_QUESTION,
    MODE3_SHOW_CORRECT,
    QUIZ_COMPLETE_MESSAGE,
)
from quiz_app.constants.quiz_constants import (
    TIME_LIMIT_TICKING_WINDOW_SECONDS,
    TICKING_SOUND_PATH,
)
from quiz_app.core.models import QuizQuestion
from quiz_app.core.quiz_manager import QuizManager
from quiz_app.ui.dialog_helpers import show_info
from quiz_app.ui.question_renderer import render_question_with_options
from quiz_app.styling.styles import Styles


class LivePanel(QWidget):
    """UI component for running a live quiz session."""

    def __init__(
        self, 
        quiz_manager: QuizManager, 
        student_url: str, 
        on_stop_session: callable,
        parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.quiz_manager = quiz_manager
        self.student_url = student_url
        self.on_stop_session = on_stop_session
        
        self._game_font_size: int = 14
        self._scoreboard_size: int = 3
        self._show_stats_always: bool = False
        
        self._active_time_limit_seconds: int | None = None
        self._active_time_limit_deadline: datetime | None = None
        self._last_tick_second: int | None = None
        self._ticking_sound_effect: QSoundEffect | None = None
        self._showing_correct_answer: bool = False

        self._build_ui()
        self._configure_time_limit_timer()
        self._setup_ticking_sound()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Top control row: Student URL
        control_row = QHBoxLayout()
        self.network_label = QLabel(f"Students connect to: {self.student_url}", self)
        self.network_label.setWordWrap(True)
        self.network_label.setStyleSheet(Styles.get_large_label_style())
        control_row.addWidget(self.network_label)
        layout.addLayout(control_row)

        # Second control row: Correct answer label and Show Correct button
        button_row = QHBoxLayout()
        self.correct_label = QLabel("Correct answer hidden", self)
        self.correct_label.setAlignment(Qt.AlignCenter)
        self.correct_label.setVisible(False)
        button_row.addWidget(self.correct_label)
        
        button_row.addStretch()
        
        self.toggle_button = QPushButton(MODE3_SHOW_CORRECT, self)
        self.toggle_button.clicked.connect(self._handle_toggle)
        self.toggle_button.setEnabled(False)
        button_row.addWidget(self.toggle_button)
        
        layout.addLayout(button_row)

        # Timer row
        timer_row = QHBoxLayout()
        self.time_limit_label = QLabel("", self)
        self.time_limit_label.setVisible(False)
        self.time_limit_label.setStyleSheet("padding: 2px 6px; border-radius: 4px;")
        timer_row.addWidget(self.time_limit_label)

        self.time_limit_progress = QProgressBar(self)
        self.time_limit_progress.setRange(0, 1000)
        self.time_limit_progress.setValue(0)
        self.time_limit_progress.setTextVisible(False)
        self.time_limit_progress.setVisible(False)
        timer_row.addWidget(self.time_limit_progress, stretch=1)

        layout.addLayout(timer_row)

        # Preview and scoreboard
        preview_row = QHBoxLayout()
        self.preview_view = QWebEngineView(self)
        preview_row.addWidget(self.preview_view, stretch=3)

        self.scoreboard_group = QGroupBox(self)
        self.scoreboard_group.setMinimumWidth(240)
        self.scoreboard_layout = QVBoxLayout()
        self.scoreboard_group.setLayout(self.scoreboard_layout)
        preview_row.addWidget(self.scoreboard_group, stretch=1)

        layout.addLayout(preview_row, stretch=1)

        self.scoreboard_labels: list[QLabel] = []

        # Stats
        stats_row = QHBoxLayout()
        self.option_stat_labels: list[QLabel] = []
        for idx, label in enumerate(("A", "B", "C", "D")):
            option_label = QLabel(f"{label}: 0%", self)
            option_label.setVisible(False)
            self.option_stat_labels.append(option_label)
            stats_row.addWidget(option_label)
        
        stats_row.addStretch()
        
        self.overall_stat_label = QLabel("Overall correctness: 0%", self)
        self.overall_stat_label.setVisible(False)
        stats_row.addWidget(self.overall_stat_label)
        
        layout.addLayout(stats_row)
        
        self._rebuild_scoreboard_labels()

    def _configure_time_limit_timer(self) -> None:
        self.time_limit_timer = QTimer(self)
        self.time_limit_timer.setInterval(100)
        self.time_limit_timer.timeout.connect(self._tick_time_limit_indicator)

    def _setup_ticking_sound(self) -> None:
        path_setting = TICKING_SOUND_PATH
        if not path_setting:
            return
        sound_path = Path(path_setting)
        if not sound_path.is_absolute():
            # Assuming project root is 3 levels up from here (quiz_app/ui/components/live_panel.py -> quiz_app/ui/components -> quiz_app/ui -> quiz_app -> root)
            # Wait, the original code was in quiz_app/ui/teacher_main_window.py (2 levels up from quiz_app).
            # Here we are in quiz_app/ui/components/live_panel.py.
            # __file__ -> components -> ui -> quiz_app -> root. So 4 parents?
            # Let's be safe and use a relative path from the module location if possible, or just assume CWD if running from root.
            # The original code used: Path(__file__).resolve().parents[2]
            # If I am at quiz_app/ui/components/live_panel.py:
            # parent 0: components
            # parent 1: ui
            # parent 2: quiz_app
            # parent 3: root (where app_main.py likely is)
            project_root = Path(__file__).resolve().parents[3]
            sound_path = project_root / sound_path
        if not sound_path.exists():
            return
        effect = QSoundEffect(self)
        effect.setSource(QUrl.fromLocalFile(str(sound_path)))
        loop_value = getattr(QSoundEffect, "Infinite", -1)
        if hasattr(loop_value, "value"):
            loop_value = loop_value.value
        effect.setLoopCount(int(loop_value))
        effect.setVolume(0.6)
        self._ticking_sound_effect = effect

    def start_session(self) -> bool:
        self.quiz_manager.reset_quiz_progress()
        question = self.quiz_manager.move_to_next_question()
        if question is None:
            show_info(self, "Quiz complete", QUIZ_COMPLETE_MESSAGE)
            return False

        self.toggle_button.setEnabled(True)
        self._showing_correct_answer = False
        self._update_next_question_button_label()
        self._hide_stats()
        self._display_question(question)
        return True

    def stop_session(self) -> None:
        self.quiz_manager.stop_current_question()
        self.quiz_manager.reset_quiz_progress()
        self.toggle_button.setEnabled(False)
        self.correct_label.setVisible(False)
        self._hide_time_limit_indicator()
        if hasattr(self, "answers_received_label"):
            self.answers_received_label.setText("Answers received: 0")

    def _handle_toggle(self) -> None:
        if not self._showing_correct_answer:
            # Show correct answer
            self.quiz_manager.stop_current_question()
            self._hide_time_limit_indicator()
            question = self.quiz_manager.get_current_question()
            correct_index = self.quiz_manager.get_current_display_correct_index()
            if question and correct_index is not None:
                letter = chr(ord("A") + correct_index)
                self.correct_label.setText(f"Correct answer: {letter}")
            else:
                self.correct_label.setText("Correct answer unavailable")
            self.correct_label.setVisible(True)
            self._show_stats()
            self._showing_correct_answer = True
            self._update_next_question_button_label()
        else:
            # Load next question
            question = self.quiz_manager.move_to_next_question()
            if question is None:
                show_info(self, "Quiz complete", QUIZ_COMPLETE_MESSAGE)
                self.on_stop_session()
                return
            self.correct_label.setVisible(False)
            self._hide_stats()
            self._showing_correct_answer = False
            self._update_next_question_button_label()
            self._display_question(question)

    def _display_question(self, question: QuizQuestion) -> None:
        self.update_student_url(self.student_url)
        options = self.quiz_manager.get_current_display_options()
        html = render_question_with_options(question.question_text, options, self._game_font_size)
        self.preview_view.setHtml(html)
        self.update_stats()
        self._update_scoreboard_view()
        self._configure_time_limit_indicator(question)

    def update_stats(self) -> None:
        counts = self.quiz_manager.get_option_counts()
        answer_total = sum(counts)
        divisor = answer_total or 1
        for idx, label in enumerate(self.option_stat_labels):
            percentage = (counts[idx] / divisor) * 100
            label.setText(f"{chr(ord('A') + idx)}: {percentage:.0f}%")

        overall = self.quiz_manager.get_overall_correctness_percentage()
        self.overall_stat_label.setText(f"Overall correctness: {overall:.0f}%")
        if hasattr(self, "answers_received_label"):
            self.answers_received_label.setText(f"Answers received: {answer_total}")
        self._update_scoreboard_view()

    def update_student_url(self, url: str) -> None:
        self.student_url = url
        self.network_label.setText(f"Students connect to: {url}")

    def set_game_font_size(self, size: int) -> None:
        self._game_font_size = size
        self.apply_font_size(size)

    def set_scoreboard_size(self, size: int) -> None:
        self._scoreboard_size = size
        self._rebuild_scoreboard_labels()
        self._update_scoreboard_view()

    def set_show_stats_always(self, enabled: bool) -> None:
        self._show_stats_always = enabled
        if enabled:
            self._show_stats()
        elif not self._showing_correct_answer:
            self._hide_stats()

    def _show_stats(self) -> None:
        for label in self.option_stat_labels:
            label.setVisible(True)
        self.overall_stat_label.setVisible(True)

    def _hide_stats(self) -> None:
        if self._show_stats_always:
            return
        for label in self.option_stat_labels:
            label.setVisible(False)
        self.overall_stat_label.setVisible(False)

    def _update_next_question_button_label(self) -> None:
        if self._showing_correct_answer:
            remaining = self.quiz_manager.get_remaining_question_count()
            self.toggle_button.setText(f"{MODE3_NEXT_QUESTION} ({remaining} Q left)")
        else:
            self.toggle_button.setText(MODE3_SHOW_CORRECT)

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

        self.answers_received_label = QLabel("Answers received: 0", self)
        self.answers_received_label.setAlignment(Qt.AlignLeft)
        self.scoreboard_layout.addWidget(self.answers_received_label)

        self.scoreboard_layout.addStretch()
        self.scoreboard_group.setTitle(f"Top {self._scoreboard_size}")
        self.apply_font_size(self._game_font_size)

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

    def _configure_time_limit_indicator(self, question: QuizQuestion) -> None:
        time_limit = question.time_limit_seconds
        started_at = self.quiz_manager.get_current_question_start_time()
        if time_limit is None or started_at is None:
            self._hide_time_limit_indicator()
            return
        self._active_time_limit_seconds = time_limit
        self._active_time_limit_deadline = started_at + timedelta(seconds=time_limit)
        self._last_tick_second = None
        self._set_time_limit_label_emphasis(enabled=False)
        self.time_limit_label.setVisible(True)
        self.time_limit_progress.setVisible(True)
        if not self.time_limit_timer.isActive():
            self.time_limit_timer.start()
        self._tick_time_limit_indicator()

    def _tick_time_limit_indicator(self) -> None:
        if (
            self._active_time_limit_seconds is None
            or self._active_time_limit_deadline is None
            or not hasattr(self, "time_limit_progress")
        ):
            self._hide_time_limit_indicator()
            return
        total_seconds = self._active_time_limit_seconds
        remaining = (self._active_time_limit_deadline - datetime.utcnow()).total_seconds()
        if remaining <= 0:
            remaining = 0
            self.time_limit_timer.stop()
        fraction = 0.0 if total_seconds <= 0 else max(0.0, min(1.0, remaining / total_seconds))
        self.time_limit_progress.setValue(int(fraction * 1000))
        if remaining > 0:
            seconds_left = max(0, math.ceil(remaining))
            self.time_limit_label.setText(f"{seconds_left}s remaining")
            self._maybe_play_time_limit_tick(seconds_left)
        else:
            self.time_limit_label.setText("Time limit reached")
            self._maybe_play_time_limit_tick(0)

    def _hide_time_limit_indicator(self) -> None:
        self._active_time_limit_seconds = None
        self._active_time_limit_deadline = None
        self._last_tick_second = None
        self._stop_ticking_sound()
        self._set_time_limit_label_emphasis(enabled=False)
        if hasattr(self, "time_limit_progress"):
            self.time_limit_progress.setVisible(False)
            self.time_limit_progress.setValue(0)
        if hasattr(self, "time_limit_label"):
            self.time_limit_label.setVisible(False)
            self.time_limit_label.setText("")
        if hasattr(self, "time_limit_timer") and self.time_limit_timer.isActive():
            self.time_limit_timer.stop()

    def _maybe_play_time_limit_tick(self, seconds_left: int) -> None:
        if seconds_left < 0:
            return
        in_window = (
            self._active_time_limit_seconds is not None
            and seconds_left <= min(TIME_LIMIT_TICKING_WINDOW_SECONDS, self._active_time_limit_seconds)
        )

        if seconds_left == 0:
            self._stop_ticking_sound()
            self._set_time_limit_label_emphasis(enabled=False)
        elif in_window:
            if self._ticking_sound_effect is not None:
                self._start_ticking_sound()
            self._set_time_limit_label_emphasis(
                enabled=True,
                blink_state=(seconds_left % 2 == 0),
            )
        else:
            self._stop_ticking_sound()
            self._set_time_limit_label_emphasis(enabled=False)

        self._last_tick_second = seconds_left

    def _start_ticking_sound(self) -> None:
        if self._ticking_sound_effect is None:
            return
        if not self._ticking_sound_effect.isPlaying():
            self._ticking_sound_effect.play()

    def _stop_ticking_sound(self) -> None:
        if self._ticking_sound_effect is None:
            return
        if self._ticking_sound_effect.isPlaying():
            self._ticking_sound_effect.stop()

    def _set_time_limit_label_emphasis(self, enabled: bool, blink_state: bool = False) -> None:
        if not hasattr(self, "time_limit_label"):
            return
        base_style = f"padding: 2px 6px; border-radius: 4px; font-size: {self._game_font_size}pt;"
        if not enabled:
            self.time_limit_label.setStyleSheet(base_style)
            return
        background = "#b91c1c" if blink_state else "#ef4444"
        self.time_limit_label.setStyleSheet(
            base_style + f" color: #fff; background-color: {background};"
        )

    def apply_font_size(self, font_size: int) -> None:
        self._game_font_size = font_size
        
        network_style = f"font-size: {font_size}pt; font-weight: bold;"
        self.network_label.setStyleSheet(network_style)
        
        game_label_style = f"font-size: {font_size}pt;"
        self.correct_label.setStyleSheet(game_label_style)
        self.toggle_button.setStyleSheet(game_label_style)
        self.time_limit_label.setStyleSheet(game_label_style)
        self.time_limit_progress.setStyleSheet(f"QProgressBar {{ font-size: {font_size}pt; }}")
        
        for label in self.scoreboard_labels:
            label.setStyleSheet(game_label_style)
        if hasattr(self, "answers_received_label"):
            self.answers_received_label.setStyleSheet(game_label_style)
            
        self.scoreboard_group.setStyleSheet(f"font-size: {font_size}pt; font-weight: bold;")
        
        for label in self.option_stat_labels:
            label.setStyleSheet(game_label_style)
        self.overall_stat_label.setStyleSheet(game_label_style)
        
        # Refresh preview if active
        if self.quiz_manager.get_current_question():
             self._display_question(self.quiz_manager.get_current_question())
