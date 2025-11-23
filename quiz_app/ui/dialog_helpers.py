"""Helper functions for common dialog patterns in the teacher UI."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QMessageBox, QWidget


def _apply_optional_font(widget: QWidget, font_point_size: int | None) -> None:
    """Apply font size to a widget when requested."""
    if font_point_size is None or font_point_size <= 0:
        return

    font: QFont = widget.font()
    font.setPointSize(font_point_size)
    widget.setFont(font)


def confirm_delete_question(parent: QWidget, question_number: int) -> bool:
    """Show confirmation dialog for deleting a question.
    
    Args:
        parent: Parent widget for the dialog
        question_number: The question number to display (1-indexed)
    
    Returns:
        True if user confirmed, False otherwise
    """
    reply = QMessageBox.question(
        parent,
        "Confirm Delete",
        f"Are you sure you want to delete question {question_number}?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    return reply == QMessageBox.Yes


def confirm_new_quiz(parent: QWidget) -> bool:
    """Show confirmation dialog for creating a new quiz.
    
    Args:
        parent: Parent widget for the dialog
    
    Returns:
        True if user confirmed, False otherwise
    """
    reply = QMessageBox.question(
        parent,
        "Confirm New Quiz",
        "Creating a new quiz will delete the existing quiz. Continue?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    return reply == QMessageBox.Yes


def confirm_import_quiz(parent: QWidget) -> bool:
    """Show confirmation dialog for importing a quiz.
    
    Args:
        parent: Parent widget for the dialog
    
    Returns:
        True if user confirmed, False otherwise
    """
    reply = QMessageBox.question(
        parent,
        "Confirm Import",
        "Importing a quiz will replace the current quiz. Continue?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    return reply == QMessageBox.Yes


def check_unsaved_changes(parent: QWidget) -> bool | None:
    """Show dialog asking user about unsaved changes.
    
    Args:
        parent: Parent widget for the dialog
    
    Returns:
        True if user wants to save, False if discard, None if cancelled
    """
    reply = QMessageBox.question(
        parent,
        "Unsaved Changes",
        "Question is not saved. Do you want to save the question?",
        QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
        QMessageBox.Yes
    )
    
    if reply == QMessageBox.Yes:
        return True
    elif reply == QMessageBox.No:
        return False
    else:  # Cancel
        return None


def show_error(parent: QWidget, title: str, message: str) -> None:
    """Show error dialog.
    
    Args:
        parent: Parent widget for the dialog
        title: Dialog title
        message: Error message
    """
    QMessageBox.critical(parent, title, message)


def show_info(
    parent: QWidget,
    title: str,
    message: str,
    *,
    font_point_size: int | None = None,
) -> None:
    """Show information dialog.
    
    Args:
        parent: Parent widget for the dialog
        title: Dialog title
        message: Information message
    """
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Information)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setStandardButtons(QMessageBox.Ok)
    _apply_optional_font(msg_box, font_point_size)
    if font_point_size is not None and font_point_size > 0:
        msg_box.setStyleSheet(
            f"QLabel {{ font-size: {font_point_size}pt; }}\n"
            f"QPushButton {{ font-size: {font_point_size}pt; }}"
        )
    msg_box.exec()


def show_warning(parent: QWidget, title: str, message: str) -> None:
    """Show warning dialog.
    
    Args:
        parent: Parent widget for the dialog
        title: Dialog title
        message: Warning message
    """
    QMessageBox.warning(parent, title, message)
