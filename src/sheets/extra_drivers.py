"""Extra Drivers tab — profiles for drivers not in the hardcoded roster.

Rows are created automatically when substitution detection meets a driver
the app has never seen (src/sub_detection.py). Edit them freely in the sheet
(e.g. fill in Country); they're merged into seed_data.SUBSTITUTE_DRIVERS on
startup.

Sheet layout:
  | Number | Name | Team | Acronym | Country | Headshot URL |
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.sheets.client import SheetsClient

logger = logging.getLogger(__name__)

WORKSHEET_TITLE = "Extra Drivers"
HEADERS = ["Number", "Name", "Team", "Acronym", "Country", "Headshot URL"]


def read_extra_drivers(client: "SheetsClient") -> list[dict]:
    try:
        rows = client.read_all_values(WORKSHEET_TITLE)
    except Exception:
        logger.info("Extra Drivers tab not found — no extra driver profiles")
        return []
    drivers = []
    for row in rows[1:]:
        row = row + [""] * (len(HEADERS) - len(row))
        if not row[1].strip():
            continue
        try:
            number = int(row[0]) if str(row[0]).strip() else 0
        except ValueError:
            number = 0
        drivers.append({
            "number": number,
            "name": row[1].strip(),
            "team": row[2].strip(),
            "acronym": row[3].strip(),
            "country": row[4].strip(),
            "headshot_url": row[5].strip(),
        })
    logger.info(f"Loaded {len(drivers)} extra driver profiles")
    return drivers


def write_extra_drivers(client: "SheetsClient", drivers: list[dict]) -> None:
    rows = [HEADERS] + [
        [d["number"], d["name"], d["team"], d["acronym"], d.get("country", ""),
         d.get("headshot_url", "")]
        for d in drivers
    ]
    client.write_all_values(WORKSHEET_TITLE, rows)
    logger.info(f"Wrote {len(drivers)} extra driver profiles")
