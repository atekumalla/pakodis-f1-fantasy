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
# For 2026: 24 rounds originally, but Bahrain (R4) & Saudi Arabia (R5) canceled,
# leaving 22 ACTIVE races. The live calendar RENUMBERS active races 1..22, so the
# mid-season redraft fires after the Hungarian GP. With the renumbered schedule the
# Hungarian GP is round 11 (per the league's counting), so races 1-11 are H1 and
# races 12+ are H2. Override with the HALFWAY_ROUND env var if needed.
HALFWAY_ROUND = int(os.getenv("HALFWAY_ROUND", "11"))

# Number of drivers each player drafts in the mid-season redraft.
# 4 players x 5 drivers = 20 total picks (out of 22 active drivers).
DRIVERS_PER_PLAYER = int(os.getenv("DRIVERS_PER_PLAYER", "5"))


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

    # --- Admin ---
    # Shared password required to trigger a Force Sync via the API/UI.
    # If left blank, force sync is allowed without a password (fine for local
    # dev; set this on any public deployment).
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

    # --- Deployment ---
    PORT: int = int(os.getenv("PORT", "8000"))

    # --- Demo Mode ---
    DEMO_GOOGLE_SHEETS_ID: str = os.getenv("DEMO_GOOGLE_SHEETS_ID", "")

    # --- Draft ---
    # Each player drafts exactly this many drivers in the mid-season redraft.
    # 4 players x 5 = 20 total picks (out of 22 active drivers).
    DRAFT_PICKS_PER_PLAYER: int = int(os.getenv("DRAFT_PICKS_PER_PLAYER", "5"))

    # --- Share Message ---
    DASHBOARD_URL: str = os.getenv("DASHBOARD_URL", "")

    # --- Rate Limiting ---
    # Cooldown between manual "Sync" presses. The incremental sync is cheap
    # (~1 API call when nothing new), so this can be short and snappy.
    SYNC_COOLDOWN_SECONDS: int = int(os.getenv("SYNC_COOLDOWN_SECONDS", "90"))
    # Cooldown for the expensive "Force sync" (re-fetches everything, ~50+ calls).
    SYNC_FORCE_COOLDOWN_SECONDS: int = int(os.getenv("SYNC_FORCE_COOLDOWN_SECONDS", "600"))

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
