"""Utilities for importing quizzes from a human-friendly text file.

File format (repeat blocks separated by blank lines or '---'):

    Q: Question text (supports markdown + LaTeX). Additional lines until the
       next marker are treated as part of the question.
    A: First option text
    B: Second option text
    C: Third option text
    D: Fourth option text
    CORRECT: A|B|C|D   (optional — omit if not graded yet)
    TIMELIMIT: seconds (optional — omit for no timer)

Example:

    Q: What is $2 + 2$?
    A: 3
    B: 4
    C: 5
    D: 22
    CORRECT: B
    TIMELIMIT: 30

Architecture note:
    A structured format such as JSON/YAML would simplify parsing and allow
    tooling support, but plain text keeps the workflow close to how teachers
    already write quizzes. The importer keeps the parsing logic isolated so we
    can swap in an alternative format later without touching UI/server code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quiz_app.core.models import QuizQuestion


class QuizImportError(Exception):
    """Raised when a quiz definition cannot be parsed."""


@dataclass(slots=True)
class ImportedQuiz:
    """Container for imported quiz metadata and questions."""

    source_path: Path
    questions: list[QuizQuestion]


_OPTION_ORDER = ["A", "B", "C", "D"]


def load_quiz_from_file(file_path: Path) -> ImportedQuiz:
    text = file_path.read_text(encoding="utf-8")
    questions = _parse_quiz_text(text)
    if not questions:
        raise QuizImportError("Quiz file did not contain any questions.")
    return ImportedQuiz(source_path=file_path, questions=questions)


def _parse_quiz_text(text: str) -> list[QuizQuestion]:
    blocks: list[str] = []
    current_block: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped == "---":
            if current_block:
                blocks.append("\n".join(current_block).strip())
                current_block = []
            continue
        if stripped:
            current_block.append(raw_line)
        elif current_block:
            # Blank line encountered after content - finalize current block
            blocks.append("\n".join(current_block).strip())
            current_block = []
    if current_block:
        blocks.append("\n".join(current_block).strip())

    questions: list[QuizQuestion] = []
    for block in blocks:
        if block:
            questions.append(_parse_block(block))
    return questions


def _parse_block(block: str) -> QuizQuestion:
    question_lines: list[str] = []
    options: dict[str, str] = {}
    correct_letter: str | None = None
    time_limit_seconds: int | None = None
    current_section: str | None = None

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        upper = line.upper()
        if upper.startswith("Q:"):
            question_lines = [line[2:].strip()]
            current_section = "Q"
            continue

        if upper.startswith("CORRECT:"):
            correct_letter = line.split(":", 1)[1].strip().upper()
            current_section = None
            continue

        if upper.startswith("TIMELIMIT:"):
            raw_value = line.split(":", 1)[1].strip()
            if not raw_value:
                raise QuizImportError("TIMELIMIT must include an integer value.")
            try:
                parsed_value = int(raw_value)
            except ValueError as exc:  # pragma: no cover - conversion error details unnecessary
                raise QuizImportError("TIMELIMIT must be an integer number of seconds.") from exc
            if parsed_value <= 0:
                raise QuizImportError("TIMELIMIT must be a positive integer.")
            time_limit_seconds = parsed_value
            current_section = None
            continue

        if len(line) > 2 and line[0].upper() in _OPTION_ORDER and line[1] == ":":
            letter = line[0].upper()
            options[letter] = line[2:].strip()
            current_section = letter
            continue

        if current_section == "Q":
            question_lines.append(line)
        elif current_section in _OPTION_ORDER:
            options[current_section] = options[current_section] + f"\n{line}"
        else:
            raise QuizImportError(
                f"Encountered text outside of a known section: '{line}'."
            )

    if not question_lines:
        raise QuizImportError("Question text missing (Q: ...)")
    if len(options) != 4:
        raise QuizImportError("Each question must define exactly four options (A-D).")

    option_list = [_sanitize_option(options.get(letter, "")) for letter in _OPTION_ORDER]
    if any(not opt for opt in option_list):
        raise QuizImportError("Option text cannot be empty.")

    correct_index = None
    if correct_letter is not None:
        if correct_letter not in _OPTION_ORDER:
            raise QuizImportError("CORRECT must be one of A, B, C, or D.")
        correct_index = _OPTION_ORDER.index(correct_letter)

    question_text = "\n".join(line for line in question_lines).strip()
    if not question_text:
        raise QuizImportError("Question text cannot be empty.")

    return QuizQuestion(
        id=0,  # overwritten by QuizManager when the quiz is loaded
        question_text=question_text,
        options=option_list,
        time_limit_seconds=time_limit_seconds,
        correct_option_index=correct_index,
        is_saved=True,
    )


def _sanitize_option(option_text: str) -> str:
    return option_text.strip()
