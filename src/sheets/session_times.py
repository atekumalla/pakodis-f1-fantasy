"""Session Times sheet — caches upcoming session schedule from OpenF1 API.

Sheet layout:
  | Grand Prix | Session Name | Start Time (UTC) |

This avoids calling the OpenF1 API on every page load. Times are refreshed
during the periodic background sync.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.sheets.client import SheetsClient

logger = logging.getLogger(__name__)

WORKSHEET_TITLE = "Session Times"

HEADERS = ["Grand Prix", "Session Name", "Start Time (UTC)"]


def read_session_times(client: "SheetsClient") -> dict[str, list[dict]]:
    """Read cached session times from Google Sheets.
    
    Returns:
        Dict mapping grand_prix name → list of {name, time} dicts
    """
    try:
        data = client.read_all_values(WORKSHEET_TITLE)
    except Exception:
        logger.debug("No Session Times sheet found (will be created on first sync)")
        return {}

    if not data or len(data) < 2:
        return {}

    result: dict[str, list[dict]] = {}
    for row in data[1:]:
        if not row or len(row) < 3:
            continue
        gp_name = row[0]
        session_name = row[1]
        start_time = row[2]
        result.setdefault(gp_name, []).append({
            "name": session_name,
            "time": start_time,
            "source": "cached",
        })

    logger.info(f"Loaded session times for {len(result)} GPs from '{WORKSHEET_TITLE}'")
    return result


def write_session_times(
    client: "SheetsClient",
    times_by_gp: dict[str, list[dict]],
):
    """Write session times to Google Sheets."""
    rows = [HEADERS]
    for gp_name in sorted(times_by_gp):
        for session in times_by_gp[gp_name]:
            rows.append([
                gp_name,
                session["name"],
                session.get("time", ""),
            ])

    client.write_all_values(WORKSHEET_TITLE, rows)
    logger.info(f"Wrote session times for {len(times_by_gp)} GPs to '{WORKSHEET_TITLE}'")
