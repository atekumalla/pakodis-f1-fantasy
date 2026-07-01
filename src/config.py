"""Application configuration loaded from environment variables."""

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (only used in local dev, ignored on Render)
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

logger = logging.getLogger(__name__)

# Halfway point for the season (races 1-N are H1, races N+1 to end are H2).
# For 2026: 24 rounds originally, but Bahrain (R4) & Saudi Arabia (R5) canceled.
# With 22 active races, Round 12 (British GP) is the halfway marker.
# Races 1-12 are H1, Races 13-25 are H2.
HALFWAY_ROUND = int(os.getenv("HALFWAY_ROUND", "12"))


class Config:
    """Central configuration for the F1 2026 Fantasy Draft app."""

    # --- Google Sheets ---
    GOOGLE_SHEETS_CREDENTIALS_JSON: str = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "")
    GOOGLE_SHEETS_CREDENTIALS_FILE: str = os.getenv(
        "GOOGLE_SHEETS_CREDENTIALS_FILE",
        str(_project_root / "credentials.json"),
    )
    GOOGLE_SHEETS_ID: str = os.getenv("GOOGLE_SHEETS_ID", "")

    # --- OpenF1 API ---
    OPENF1_BASE_URL: str = os.getenv("OPENF1_BASE_URL", "https://api.openf1.org/v1")
    F1_SEASON_YEAR: int = int(os.getenv("F1_SEASON_YEAR", "2026"))

    # --- OpenAI / ChatGPT (optional validation) ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # --- Sync Schedule ---
    SYNC_INTERVAL_MINUTES: int = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))
    SYNC_LIVE_INTERVAL_SECONDS: int = int(os.getenv("SYNC_LIVE_INTERVAL_SECONDS", "120"))
    SYNC_TIMEZONE: str = os.getenv("SYNC_TIMEZONE", "Asia/Kolkata")

    # --- State ---
    STATE_FILE: str = os.getenv(
        "STATE_FILE", str(_project_root / "state" / "last_sync.json")
    )
    DRAFT_STATE_FILE: str = os.getenv(
        "DRAFT_STATE_FILE", str(_project_root / "state" / "draft_state.json")
    )

    # --- Logging ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # --- Deployment ---
    PORT: int = int(os.getenv("PORT", "8000"))

    # --- Demo Mode ---
    DEMO_GOOGLE_SHEETS_ID: str = os.getenv("DEMO_GOOGLE_SHEETS_ID", "")

    # --- Share Message ---
    DASHBOARD_URL: str = os.getenv("DASHBOARD_URL", "")

    # --- Rate Limiting ---
    SYNC_COOLDOWN_SECONDS: int = int(os.getenv("SYNC_COOLDOWN_SECONDS", "600"))

    @classmethod
    def has_credentials_json(cls) -> bool:
        """Check if credentials are provided as a JSON env var (for hosted deploys)."""
        return bool(cls.GOOGLE_SHEETS_CREDENTIALS_JSON.strip())

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of missing required config values."""
        errors = []
        if not cls.GOOGLE_SHEETS_ID:
            errors.append("GOOGLE_SHEETS_ID is not set")
        if not cls.has_credentials_json():
            if not Path(cls.GOOGLE_SHEETS_CREDENTIALS_FILE).exists():
                errors.append(
                    "Google credentials not found. Set GOOGLE_SHEETS_CREDENTIALS_JSON "
                    "(for hosted) or place credentials.json in project root (for local dev)"
                )
        return errors
