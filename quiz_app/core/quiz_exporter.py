"""Utilities for exporting quizzes to the plain-text format used for imports."""

from __future__ import annotations

from pathlib import Path

from quiz_app.core.models import QuizQuestion

_OPTION_LETTERS = ("A", "B", "C", "D")


def save_quiz_to_file(file_path: Path, questions: list[QuizQuestion]) -> None:
    """Persist the provided questions to disk in the text import format."""

    if not questions:
        raise ValueError("Cannot export an empty quiz.")

    file_path = file_path.resolve()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    document = _serialize_questions(questions)
    file_path.write_text(document, encoding="utf-8")


def _serialize_questions(questions: list[QuizQuestion]) -> str:
    blocks = [_serialize_question(question) for question in questions]
    return "\n\n---\n\n".join(blocks) + "\n"


def _serialize_question(question: QuizQuestion) -> str:
    lines: list[str] = []

    question_lines = question.question_text.splitlines() or [question.question_text]
    lines.append(f"Q: {question_lines[0] if question_lines else ''}")
    lines.extend(question_lines[1:])

    for idx, letter in enumerate(_OPTION_LETTERS):
        option_text = question.options[idx] if idx < len(question.options) else ""
        option_lines = option_text.splitlines() or [option_text]
        lines.append(f"{letter}: {option_lines[0] if option_lines else ''}")
        lines.extend(option_lines[1:])

    if question.correct_option_index is not None:
        correct_letter = _OPTION_LETTERS[question.correct_option_index]
        lines.append(f"CORRECT: {correct_letter}")

    if question.time_limit_seconds is not None:
        lines.append(f"TIMELIMIT: {question.time_limit_seconds}")

    return "\n".join(lines)
