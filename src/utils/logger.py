"""Logging setup for the F1 2026 Fantasy Draft app."""

import logging
import sys

from src.config import Config


def setup_logging():
    """Configure logging for the application."""
    level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)

    for name in ("httpx", "httpcore", "openai", "gspread", "google", "apscheduler"):
        logging.getLogger(name).setLevel(logging.WARNING)
