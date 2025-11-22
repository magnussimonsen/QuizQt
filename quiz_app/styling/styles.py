"""Centralized styles and font definitions for the application."""

from .color_palette import ColorPalette, Theme

class Styles:
    """Helper class to generate Qt stylesheets based on the current theme."""

    @staticmethod
    def get_main_window_style(theme: Theme = Theme.LIGHT) -> str:
        return f"""
            QMainWindow {{
                background-color: {ColorPalette.BACKGROUND_PRIMARY.get(theme)};
                color: {ColorPalette.TEXT_PRIMARY.get(theme)};
            }}
            QWidget {{
                background-color: {ColorPalette.BACKGROUND_PRIMARY.get(theme)};
                color: {ColorPalette.TEXT_PRIMARY.get(theme)};
                font-family: 'Segoe UI', 'Roboto', sans-serif;
                font-size: 14px;
            }}
            QLabel {{
                color: {ColorPalette.TEXT_PRIMARY.get(theme)};
            }}
            QPushButton {{
                background-color: {ColorPalette.BUTTON_SECONDARY_BG.get(theme)};
                color: {ColorPalette.TEXT_PRIMARY.get(theme)};
                border: 1px solid {ColorPalette.BORDER_PRIMARY.get(theme)};
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: {ColorPalette.BUTTON_HOVER_BG.get(theme)};
            }}
            QPushButton:checked {{
                background-color: {ColorPalette.BUTTON_PRIMARY_BG.get(theme)};
                color: {ColorPalette.BUTTON_PRIMARY_TEXT.get(theme)};
                border: 1px solid {ColorPalette.BUTTON_PRIMARY_BG.get(theme)};
            }}
            QLineEdit, QPlainTextEdit, QSpinBox, QComboBox {{
                background-color: {ColorPalette.BACKGROUND_PRIMARY.get(theme)};
                color: {ColorPalette.TEXT_PRIMARY.get(theme)};
                border: 1px solid {ColorPalette.BORDER_PRIMARY.get(theme)};
                border-radius: 4px;
                padding: 4px;
            }}
            QListWidget {{
                background-color: {ColorPalette.BACKGROUND_PRIMARY.get(theme)};
                border: 1px solid {ColorPalette.BORDER_PRIMARY.get(theme)};
                border-radius: 4px;
            }}
            QGroupBox {{
                border: 1px solid {ColorPalette.BORDER_PRIMARY.get(theme)};
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }}
        """

    @staticmethod
    def get_large_label_style() -> str:
        return "font-size: 16pt; font-weight: bold;"
