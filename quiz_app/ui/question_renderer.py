"""Question rendering utilities for displaying quiz questions."""

from __future__ import annotations

from typing import List

from quiz_app.core.markdown_math_renderer import renderer


def render_question_with_options(question_text: str, options: List[str], font_size: int = 14) -> str:
    """Render a quiz question with its options as HTML.
    
    Args:
        question_text: The question text (supports Markdown and LaTeX)
        options: List of 4 option strings
        font_size: Font size in points for the question text (default 14)
    
    Returns:
        HTML string ready for display in QWebEngineView
    """
    markdown_lines = [question_text.strip() or "(No question text)", ""]
    for idx, option in enumerate(options):
        letter = chr(ord("A") + idx)
        markdown_lines.append(f"**{letter}.** {option or '(empty)'}")
    markdown = "\n\n".join(markdown_lines)
    return renderer.render_full_document(markdown, font_size=font_size)
