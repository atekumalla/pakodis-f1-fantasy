"""F1 2026 Fantasy Draft — Main Application Entry Point.

Usage:
    python -m src.main          # Run the server
    python -m src.seed_data     # Seed the Google Sheet
"""

from __future__ import annotations

import logging

from src.config import Config
from src.server import start
from src.utils.logger import setup_logging

logger = logging.getLogger(__name__)


def main():
    """Start the F1 Fantasy Draft server."""
    setup_logging()

    errors = Config.validate()
    if errors:
        for err in errors:
            logger.warning(f"Config issue: {err}")

    start()


if __name__ == "__main__":
    main()
