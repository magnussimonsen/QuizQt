"""Color palette for QuizQt application supporting light and dark themes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class Theme(Enum):
    """Application theme options."""
    LIGHT = auto()
    DARK = auto()


@dataclass(frozen=True)
class ThemeColors:
    """Color definitions for a specific theme."""
    light: str
    dark: str
    
    def get(self, theme: Theme) -> str:
        """Get color value for the specified theme."""
        return self.light if theme == Theme.LIGHT else self.dark


class ColorPalette:
    """Centralized color definitions for the application."""
    
    # Text colors
    TEXT_PRIMARY = ThemeColors(
        light="#000000",      # Black
        dark="#F5F5F5"        # WhiteSmoke
    )
    
    TEXT_SECONDARY = ThemeColors(
        light="#666666",      # Dark Gray
        dark="#AAAAAA"        # Light Gray
    )
    
    TEXT_DISABLED = ThemeColors(
        light="#CCCCCC",      # Light Gray
        dark="#555555"        # Dark Gray
    )
    
    # Background colors
    BACKGROUND_PRIMARY = ThemeColors(
        light="#FFFFFF",      # White
        dark="#1E1E1E"        # Dark Gray
    )
    
    BACKGROUND_SECONDARY = ThemeColors(
        light="#F5F5F5",      # WhiteSmoke
        dark="#2D2D2D"        # Slightly lighter dark
    )
    
    BACKGROUND_TERTIARY = ThemeColors(
        light="#E8E8E8",      # Light Gray
        dark="#3A3A3A"        # Medium Dark Gray
    )
    
    # Accent colors
    ACCENT_PRIMARY = ThemeColors(
        light="#0078D4",      # Blue
        dark="#4A9EFF"        # Lighter Blue
    )
    
    ACCENT_SECONDARY = ThemeColors(
        light="#00B294",      # Teal
        dark="#00D9B5"        # Lighter Teal
    )
    
    # Status colors
    SUCCESS = ThemeColors(
        light="#107C10",      # Green
        dark="#6FCF6F"        # Light Green
    )
    
    WARNING = ThemeColors(
        light="#FFB900",      # Orange/Yellow
        dark="#FFC83D"        # Lighter Orange
    )
    
    ERROR = ThemeColors(
        light="#D13438",      # Red
        dark="#FF6B6B"        # Light Red
    )
    
    # Border colors
    BORDER_PRIMARY = ThemeColors(
        light="#D1D1D1",      # Gray
        dark="#555555"        # Dark Gray
    )
    
    BORDER_FOCUS = ThemeColors(
        light="#0078D4",      # Blue
        dark="#4A9EFF"        # Lighter Blue
    )
    
    # Button colors
    BUTTON_PRIMARY_BG = ThemeColors(
        light="#0078D4",      # Blue
        dark="#4A9EFF"        # Lighter Blue
    )
    
    BUTTON_PRIMARY_TEXT = ThemeColors(
        light="#FFFFFF",      # White
        dark="#000000"        # Black
    )
    
    BUTTON_SECONDARY_BG = ThemeColors(
        light="#F5F5F5",      # WhiteSmoke
        dark="#3A3A3A"        # Dark Gray
    )
    
    BUTTON_HOVER_BG = ThemeColors(
        light="#E8E8E8",      # Light Gray
        dark="#505050"        # Medium Gray
    )
    
    # Preview/Display colors
    PREVIEW_BG = ThemeColors(
        light="#FFFFFF",      # White
        dark="#252525"        # Very Dark Gray
    )
