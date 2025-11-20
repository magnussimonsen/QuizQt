"""Settings dialog for configuring QuizQt preferences."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QPushButton,
    QGroupBox,
    QCheckBox,
)


class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""

    def __init__(
        self,
        parent=None,
        ui_font_size: int = 10,
        game_font_size: int = 14,
        show_stats_always: bool = False,
        reset_aliases_on_start: bool = False,
        scoreboard_size: int = 3,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self._ui_font_size = ui_font_size
        self._game_font_size = game_font_size
        self._show_stats_always = show_stats_always
        self._reset_aliases_on_start = reset_aliases_on_start
        self._scoreboard_size = max(1, min(10, scoreboard_size))
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Font settings group
        font_group = QGroupBox("Font Sizes")
        font_layout = QVBoxLayout()
        font_group.setLayout(font_layout)
        
        # UI Font Size
        ui_font_row = QHBoxLayout()
        ui_font_label = QLabel("UI Font Size (buttons, menus):")
        ui_font_label.setToolTip("Font size for buttons, menus, and controls")
        self.ui_font_spinbox = QSpinBox()
        self.ui_font_spinbox.setRange(8, 24)
        self.ui_font_spinbox.setValue(self._ui_font_size)
        self.ui_font_spinbox.setSuffix(" pt")
        ui_font_row.addWidget(ui_font_label)
        ui_font_row.addStretch()
        ui_font_row.addWidget(self.ui_font_spinbox)
        font_layout.addLayout(ui_font_row)
        
        # Game Font Size
        game_font_row = QHBoxLayout()
        game_font_label = QLabel("Game Font Size (questions, stats):")
        game_font_label.setToolTip("Font size for live quiz display: questions, answers, and statistics")
        self.game_font_spinbox = QSpinBox()
        self.game_font_spinbox.setRange(10, 32)
        self.game_font_spinbox.setValue(self._game_font_size)
        self.game_font_spinbox.setSuffix(" pt")
        game_font_row.addWidget(game_font_label)
        game_font_row.addStretch()
        game_font_row.addWidget(self.game_font_spinbox)
        font_layout.addLayout(game_font_row)
        
        layout.addWidget(font_group)
        
        # Display settings group
        display_group = QGroupBox("Display Settings")
        display_layout = QVBoxLayout()
        display_group.setLayout(display_layout)
        
        self.show_stats_checkbox = QCheckBox("Always show statistics during questions (for development)")
        self.show_stats_checkbox.setToolTip("When enabled, answer statistics remain visible while questions are active. Useful for testing.")
        self.show_stats_checkbox.setChecked(self._show_stats_always)
        display_layout.addWidget(self.show_stats_checkbox)

        self.reset_aliases_checkbox = QCheckBox("Always reset student aliases when starting a quiz")
        self.reset_aliases_checkbox.setToolTip(
            "When enabled, every time you start live mode the student page will assign everyone a new celebrity alias."
        )
        self.reset_aliases_checkbox.setChecked(self._reset_aliases_on_start)
        display_layout.addWidget(self.reset_aliases_checkbox)

        scoreboard_row = QHBoxLayout()
        scoreboard_label = QLabel("Scoreboard slots (top N):")
        scoreboard_label.setToolTip("Number of top students shown in the live view scoreboard.")
        self.scoreboard_spinbox = QSpinBox()
        self.scoreboard_spinbox.setRange(1, 10)
        self.scoreboard_spinbox.setValue(self._scoreboard_size)
        scoreboard_row.addWidget(scoreboard_label)
        scoreboard_row.addStretch()
        scoreboard_row.addWidget(self.scoreboard_spinbox)
        display_layout.addLayout(scoreboard_row)
        
        layout.addWidget(display_group)
        
        # Buttons
        button_row = QHBoxLayout()
        button_row.addStretch()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)  # type: ignore[arg-type]
        button_row.addWidget(self.cancel_button)
        
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.accept)  # type: ignore[arg-type]
        self.apply_button.setDefault(True)
        button_row.addWidget(self.apply_button)
        
        layout.addLayout(button_row)
    
    def get_ui_font_size(self) -> int:
        """Get the selected UI font size."""
        return self.ui_font_spinbox.value()
    
    def get_game_font_size(self) -> int:
        """Get the selected game font size."""
        return self.game_font_spinbox.value()
    
    def get_show_stats_always(self) -> bool:
        """Get whether to always show statistics."""
        return self.show_stats_checkbox.isChecked()

    def get_reset_aliases_on_start(self) -> bool:
        """Get whether to reset student aliases whenever a quiz starts."""
        return self.reset_aliases_checkbox.isChecked()

    def get_scoreboard_size(self) -> int:
        """Get desired number of scoreboard slots."""
        return self.scoreboard_spinbox.value()
