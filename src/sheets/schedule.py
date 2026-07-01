"""Race Calendar sheet — manages the 'Race Calendar' tab.

Sheet layout:
  | Round | Date | Grand Prix | Circuit | Country | Has Sprint | Half | Status |
"""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

from src.config import HALFWAY_ROUND
from src.models.session import RaceWeekend

if TYPE_CHECKING:
    from src.sheets.client import SheetsClient

logger = logging.getLogger(__name__)

WORKSHEET_TITLE = "Race Calendar"

HEADERS = [
    "Round", "Date", "Grand Prix", "Circuit", "Country",
    "Has Sprint", "Half", "Status",
]


def read_calendar(client: SheetsClient) -> list[RaceWeekend]:
    """Read the race calendar from Google Sheets."""
    data = client.read_all_values(WORKSHEET_TITLE)

    if not data or len(data) < 2:
        logger.warning("No calendar data found in sheet")
        return []

    weekends = []
    for row in data[1:]:
        if not row or len(row) < 5:
            continue
        try:
            weekends.append(RaceWeekend(
                meeting_key=0,
                round_number=int(row[0]) if row[0] else 0,
                race_date=date.fromisoformat(row[1]) if row[1] else date.today(),
                name=row[2],
                circuit=row[3],
                country=row[4],
                has_sprint=row[5].lower() == "yes" if len(row) > 5 else False,
                status=row[7] if len(row) > 7 else "scheduled",
            ))
        except Exception as e:
            logger.warning(f"Failed to parse calendar row: {e}")

    logger.info(f"Loaded {len(weekends)} race weekends from sheet")
    return weekends


def write_calendar(client: SheetsClient, weekends: list[RaceWeekend]):
    """Write the race calendar to Google Sheets."""
    rows = [HEADERS]
    for w in sorted(weekends, key=lambda x: x.round_number):
        half = "H1" if w.round_number <= HALFWAY_ROUND else "H2"
        rows.append([
            w.round_number,
            w.race_date.isoformat(),
            w.name,
            w.circuit,
            w.country,
            "Yes" if w.has_sprint else "No",
            half,
            w.status,
        ])

    client.write_all_values(WORKSHEET_TITLE, rows)
    logger.info(f"Wrote {len(weekends)} race weekends to '{WORKSHEET_TITLE}'")
