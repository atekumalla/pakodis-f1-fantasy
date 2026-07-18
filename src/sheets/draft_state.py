"""Durable draft-state persistence backed by Google Sheets.

Render's free tier uses ephemeral disk — a redeploy wipes state/draft_state.json
and the in-progress draft would reset to NOT_STARTED. To make the draft durable
we mirror the full draft state into a dedicated worksheet ("Draft State") as JSON.

Layout of the "Draft State" tab:
  A1: "state_json"   (header)
  A2: <full DraftState JSON blob>

We also write a human-readable "Draft Picks Log" tab (one row per pick) so the
picks are legible in the spreadsheet, but the JSON blob in "Draft State" is the
authoritative record used to rebuild the DraftManager on startup.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.sheets.client import SheetsClient

logger = logging.getLogger(__name__)

STATE_WORKSHEET = "Draft State"
PICKS_LOG_WORKSHEET = "Draft Picks Log"


class SheetsDraftBackend:
    """Persists/loads the mid-season draft state to a Google Sheets tab.

    Implements the interface expected by DraftManager:
      - load_state() -> dict | None
      - save_state(dict) -> None
    """

    def __init__(self, client: "SheetsClient"):
        self.client = client

    def load_state(self) -> Optional[dict]:
        """Read the JSON draft state blob from the sheet, or None if absent."""
        try:
            rows = self.client.read_all_values(STATE_WORKSHEET)
        except Exception as e:
            logger.debug(f"No '{STATE_WORKSHEET}' tab yet: {e}")
            return None

        # Expect the JSON blob in cell A2.
        if not rows or len(rows) < 2 or not rows[1] or not rows[1][0].strip():
            return None

        try:
            return json.loads(rows[1][0])
        except json.JSONDecodeError as e:
            logger.warning(f"Corrupt draft state JSON in sheet: {e}")
            return None

    def save_state(self, payload: dict) -> None:
        """Write the full draft state JSON blob + a readable picks log."""
        blob = json.dumps(payload, separators=(",", ":"))
        # A1 header + A2 blob. write_all_values clears the tab first.
        self.client.write_all_values(
            STATE_WORKSHEET,
            [["state_json"], [blob]],
            clear_first=True,
        )
        self._write_picks_log(payload)

    def _write_picks_log(self, payload: dict) -> None:
        """Mirror picks into a human-readable log tab (best-effort)."""
        try:
            picks = payload.get("picks", [])
            rows: list[list] = [["Pick #", "Player", "Driver", "Timestamp"]]
            for p in picks:
                rows.append([
                    p.get("pick_number", ""),
                    p.get("player_name", ""),
                    p.get("driver_name", ""),
                    p.get("timestamp", ""),
                ])
            self.client.write_all_values(PICKS_LOG_WORKSHEET, rows, clear_first=True)
        except Exception as e:
            logger.debug(f"Could not write picks log: {e}")
