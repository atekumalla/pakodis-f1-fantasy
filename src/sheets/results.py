"""Session Results sheet — manages the 'Session Results' tab.

Sheet layout:
  | Date | Round | Grand Prix | Session | Half | Driver | # | Position | DNF | Points |

This module supports:
  - Writing session results to the sheet (after fetching from API)
  - Reading session results from the sheet (on startup, to avoid re-fetching)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from typing import TYPE_CHECKING

from src.models.session import Session, SessionResult, SessionStatus, SessionType

if TYPE_CHECKING:
    from src.sheets.client import SheetsClient
    from src.scoring.calculator import ScoringCalculator

logger = logging.getLogger(__name__)

WORKSHEET_TITLE = "Session Results"

HEADERS = [
    "Date", "Round", "Grand Prix", "Session", "Half",
    "Driver", "#", "Position", "DNF", "Points",
]


def read_results(client: "SheetsClient") -> list[Session]:
    """Read session results from Google Sheets and reconstruct Session objects.
    
    This is used on startup to load historical results without hitting the API.
    """
    data = client.read_all_values(WORKSHEET_TITLE)
    
    if not data or len(data) < 2:
        logger.info("No session results found in sheet")
        return []
    
    # Load calendar to get country info
    from src.seed_data import CALENDAR_2026
    round_to_country = {r["round"]: r["country"] for r in CALENDAR_2026}
    
    # Group rows by session (date + grand_prix + session_name)
    session_rows: dict[tuple, list[list]] = defaultdict(list)
    
    for row in data[1:]:
        if not row or len(row) < 6:
            continue
        try:
            # Key: (date, round, grand_prix, session_name)
            key = (row[0], row[1], row[2], row[3])
            session_rows[key].append(row)
        except Exception as e:
            logger.warning(f"Failed to parse result row: {e}")
    
    sessions = []
    for (date_str, round_num, grand_prix, session_name), rows in session_rows.items():
        try:
            # Parse session type from session name
            session_type = _parse_session_type(session_name)
            half = rows[0][4] if len(rows[0]) > 4 else "H1"
            
            # Build results list
            results = []
            for row in rows:
                driver_name = row[5] if len(row) > 5 else ""
                driver_number = int(row[6]) if len(row) > 6 and row[6] else 0
                position_str = str(row[7]) if len(row) > 7 else ""
                dnf_str = row[8] if len(row) > 8 else ""
                
                # Parse position
                position = None
                if position_str.isdigit():
                    position = int(position_str)
                
                results.append(SessionResult(
                    driver_name=driver_name,
                    driver_number=driver_number,
                    position=position,
                    dnf=dnf_str == "DNF",
                    dns=dnf_str == "DNS",
                    dsq=dnf_str == "DSQ",
                ))
            
            # Create session object
            # Generate a synthetic session key from round + session type
            type_offset = {"qualifying": 1, "sprint": 2, "race": 3}.get(session_type.value, 0)
            session_key = int(round_num) * 100 + type_offset
            
            # Get country from calendar
            country = round_to_country.get(int(round_num), "")
            
            session = Session(
                session_key=session_key,
                meeting_key=int(round_num) * 10,  # Synthetic
                session_date=date.fromisoformat(date_str),
                session_name=session_name,
                session_type=session_type,
                grand_prix=grand_prix,
                round_number=int(round_num),
                country=country,
                status=SessionStatus.FINISHED,
                results=results,
            )
            sessions.append(session)
            
        except Exception as e:
            logger.warning(f"Failed to reconstruct session {grand_prix} {session_name}: {e}")
    
    logger.info(f"Loaded {len(sessions)} sessions from '{WORKSHEET_TITLE}'")
    return sessions


def _parse_session_type(session_name: str) -> SessionType:
    """Parse session type from session name string."""
    name_lower = session_name.lower()
    if "race" in name_lower and "sprint" not in name_lower:
        return SessionType.RACE
    elif "sprint" in name_lower:
        return SessionType.SPRINT
    elif "quali" in name_lower:
        return SessionType.QUALIFYING
    else:
        return SessionType.RACE  # Default


def write_results(
    client: SheetsClient,
    sessions: list[Session],
    calculator: "ScoringCalculator",
):
    """Write all session results to Google Sheets."""
    rows = [HEADERS]

    for session in sorted(sessions, key=lambda s: (s.session_date, s.session_type.value)):
        if not session.is_finished and not session.is_live:
            continue

        pts_map = calculator.calculate_session_points(session)

        for result in sorted(session.results, key=lambda r: r.position if r.position else 99):
            status_str = ""
            if result.dnf:
                status_str = "DNF"
            elif result.dns:
                status_str = "DNS"
            elif result.dsq:
                status_str = "DSQ"

            rows.append([
                session.session_date.isoformat(),
                session.round_number,
                session.grand_prix,
                session.session_name,
                session.half,
                result.driver_name,
                result.driver_number,
                result.position if result.position else status_str,
                status_str,
                pts_map.get(result.driver_name, 0.0),
            ])

    client.write_all_values(WORKSHEET_TITLE, rows)
    logger.info(f"Wrote {len(rows) - 1} result rows to '{WORKSHEET_TITLE}'")
