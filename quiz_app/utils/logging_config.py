"""Logging configuration helpers for the quiz application."""

from __future__ import annotations

import logging
from logging import Logger


def configure_logging() -> Logger:
    """Configure basic logging for the application and return the root logger."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger("quiz_app")
