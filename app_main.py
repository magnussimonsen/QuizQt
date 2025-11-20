"""Application entry point for the QuizQt prototype."""

from __future__ import annotations

import socket
import sys

from PySide6.QtWidgets import QApplication

from quiz_app.constants.network_constants import DEFAULT_HOST, DEFAULT_PORT
from quiz_app.core.quiz_manager import QuizManager
from quiz_app.server.api_server import start_api_server
from quiz_app.ui.teacher_main_window import TeacherMainWindow
from quiz_app.utils.logging_config import configure_logging


def _determine_student_url(port: int) -> str:
    """Best-effort determination of the local IP for student-facing URL."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip_address = sock.getsockname()[0]
    except OSError:
        ip_address = "127.0.0.1"
    return f"http://{ip_address}:{port}/"


def main() -> None:
    """Initialize logging, start the API server, and launch the Qt UI."""
    logger = configure_logging()
    logger.info("Starting QuizQt prototype…")

    quiz_manager = QuizManager()
    start_api_server(quiz_manager=quiz_manager, host=DEFAULT_HOST, port=DEFAULT_PORT)
    student_url = _determine_student_url(DEFAULT_PORT)
    logger.info("Student page available at %s", student_url)

    app = QApplication(sys.argv)
    window = TeacherMainWindow(quiz_manager=quiz_manager, student_url=student_url)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
