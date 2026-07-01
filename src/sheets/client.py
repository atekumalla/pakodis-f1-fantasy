"""Google Sheets client using gspread with service account authentication.

Supports two credential modes:
  1. GOOGLE_SHEETS_CREDENTIALS_JSON env var (for hosted services like Render)
  2. credentials.json file (for local development)

Sheet tabs:
  Draft Picks H1  — First-half driver ownership
  Draft Picks H2  — Second-half driver ownership (after mid-season redraft)
  Race Calendar   — All 24 race weekends
  Session Results — Per-driver results for every scored session
  Leaderboard     — Current standings with H1/H2/Total breakdown
  Scoring Rules   — Points tables for reference
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from src.config import Config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsClient:
    """Wrapper around gspread for managing the fantasy draft spreadsheet."""

    def __init__(
        self,
        credentials_json: str | None = None,
        credentials_file: str | None = None,
        spreadsheet_id: str | None = None,
    ):
        self.credentials_json = credentials_json or Config.GOOGLE_SHEETS_CREDENTIALS_JSON
        self.credentials_file = credentials_file or Config.GOOGLE_SHEETS_CREDENTIALS_FILE
        self.spreadsheet_id = spreadsheet_id or Config.GOOGLE_SHEETS_ID
        self._gc: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None

    @property
    def gc(self) -> gspread.Client:
        if self._gc is None:
            creds = self._load_credentials()
            self._gc = gspread.authorize(creds)
            logger.info("Authenticated with Google Sheets API")
        return self._gc

    def _load_credentials(self) -> Credentials:
        if self.credentials_json and self.credentials_json.strip():
            logger.info("Loading Google credentials from GOOGLE_SHEETS_CREDENTIALS_JSON env var")
            info = json.loads(self.credentials_json)
            return Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            logger.info(f"Loading Google credentials from file: {self.credentials_file}")
            return Credentials.from_service_account_file(
                self.credentials_file, scopes=SCOPES
            )

    @property
    def spreadsheet(self) -> gspread.Spreadsheet:
        if self._spreadsheet is None:
            self._spreadsheet = self.gc.open_by_key(self.spreadsheet_id)
            logger.info(f"Opened spreadsheet: {self._spreadsheet.title}")
        return self._spreadsheet

    def get_or_create_worksheet(self, title: str, rows: int = 200, cols: int = 20) -> gspread.Worksheet:
        try:
            return self.spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            logger.info(f"Creating worksheet: {title}")
            return self.spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

    def read_all_values(self, worksheet_title: str) -> list[list[str]]:
        ws = self.get_or_create_worksheet(worksheet_title)
        return ws.get_all_values()

    def write_all_values(self, worksheet_title: str, values: list[list], clear_first: bool = True):
        ws = self.get_or_create_worksheet(worksheet_title)
        if clear_first:
            ws.clear()
        if values:
            ws.update(range_name="A1", values=values)
            logger.info(f"Wrote {len(values)} rows to '{worksheet_title}'")

    def update_cell(self, worksheet_title: str, row: int, col: int, value):
        ws = self.get_or_create_worksheet(worksheet_title)
        ws.update_cell(row, col, value)

    def update_range(self, worksheet_title: str, range_str: str, values: list[list]):
        ws = self.get_or_create_worksheet(worksheet_title)
        ws.update(range_name=range_str, values=values)

    def batch_update(self, worksheet_title: str, updates: list[dict]):
        ws = self.get_or_create_worksheet(worksheet_title)
        ws.batch_update(updates)
