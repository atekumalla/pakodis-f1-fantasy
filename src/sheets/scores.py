"""Leaderboard sheet — manages the 'Leaderboard' tab in Google Sheets.

Sheet layout:
  | Rank | Player | H1 Pts | H2 Pts | Total Pts | Driver 1 (pts) | ... | Driver 5 (pts) |

Shows both halves and combined total. Driver columns show H1 drivers
first, then H2 drivers (if different after redraft).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.models.session import Session
from src.models.player import DraftPlayer
from src.scoring.calculator import ScoringCalculator

if TYPE_CHECKING:
    from src.sheets.client import SheetsClient

logger = logging.getLogger(__name__)

WORKSHEET_TITLE = "Leaderboard"


def write_leaderboard(
    client: SheetsClient,
    players: list[DraftPlayer],
    sessions: list[Session],
    calculator: ScoringCalculator,
):
    """Calculate and write the leaderboard to Google Sheets."""
    leaderboard = calculator.build_leaderboard(players, sessions)

    # Determine if H2 is active
    has_h2 = any(p.drivers_h2 for p in players)

    # Build header
    header = ["Rank", "Player", "H1 Pts", "H2 Pts", "Total Pts"]
    # Add H1 driver columns
    for i in range(5):
        header.append(f"H1 Driver {i+1}")
    if has_h2:
        for i in range(5):
            header.append(f"H2 Driver {i+1}")
        header.append("H2 Sub Drivers")

    rows = [header]

    for rank, entry in enumerate(leaderboard, start=1):
        row = [
            rank,
            entry["name"],
            entry["h1"],
            entry["h2"],
            entry["total"],
        ]

        # H1 driver details
        for i in range(5):
            if i < len(entry["drivers_h1"]):
                d = entry["drivers_h1"][i]
                row.append(f"{d['name']} ({d['points']})")
            else:
                row.append("")

        # H2 driver details (regular picks, then subs)
        if has_h2:
            regular = [d for d in entry.get("drivers_h2", []) if not d.get("is_substitute")]
            subs = [d for d in entry.get("drivers_h2", []) if d.get("is_substitute")]
            for i in range(5):
                if i < len(regular):
                    d = regular[i]
                    suffix = " *" if d.get("has_substitutions") else ""
                    row.append(f"{d['name']} ({d['points']}){suffix}")
                else:
                    row.append("")
            sub_parts = [f"{d['name']} (sub for {d.get('substitute_for','?')}) ({d['points']})" for d in subs]
            row.append("; ".join(sub_parts) if sub_parts else "")

        rows.append(row)

    client.write_all_values(WORKSHEET_TITLE, rows)
    logger.info(f"Updated leaderboard with {len(leaderboard)} players")
    return leaderboard
