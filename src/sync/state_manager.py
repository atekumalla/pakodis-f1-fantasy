"""State manager — persists sync state to disk for crash recovery."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.config import Config

logger = logging.getLogger(__name__)


class StateManager:
    """Manages persistent state so the app can resume after restart."""

    def __init__(self, state_file: str | None = None):
        self.state_file = Path(state_file or Config.STATE_FILE)
        self.state: dict = self._load()

    def _load(self) -> dict:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    logger.info(f"Loaded state from {self.state_file}")
                    return state
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load state file: {e}")
        return self._default_state()

    def _default_state(self) -> dict:
        return {
            "last_sync": None,
            "last_updated": None,
            "scored_session_keys": [],
            "sync_count": 0,
            "last_error": None,
        }

    def save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2, default=str)

    @property
    def last_sync(self) -> Optional[str]:
        return self.state.get("last_sync")

    @property
    def scored_session_keys(self) -> list[int]:
        return self.state.get("scored_session_keys", [])

    def mark_synced(self):
        now = datetime.now(timezone.utc).isoformat()
        self.state["last_sync"] = now
        self.state["last_updated"] = now
        self.state["sync_count"] = self.state.get("sync_count", 0) + 1
        self.state["last_error"] = None
        self.save()

    def mark_session_scored(self, session_key: int):
        if session_key not in self.state["scored_session_keys"]:
            self.state["scored_session_keys"].append(session_key)
            self.save()

    def is_session_scored(self, session_key: int) -> bool:
        return session_key in self.state.get("scored_session_keys", [])

    def record_error(self, error: str):
        self.state["last_error"] = {
            "message": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.save()

    def get_unscored_sessions(self, sessions: list) -> list:
        scored_keys = set(self.scored_session_keys)
        return [s for s in sessions if s.session_key not in scored_keys]
