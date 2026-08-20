"""Google Sheets integration for the Substitutions tab."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.substitutions import DriverSubstitution, ACTIVE_SUBSTITUTIONS

if TYPE_CHECKING:
    from src.sheets.client import SheetsClient

logger = logging.getLogger(__name__)

WORKSHEET_TITLE = "Substitutions"


def read_substitutions(client: SheetsClient) -> list[DriverSubstitution]:
    """Read substitutions from the sheet. Falls back to code defaults if tab is missing/empty."""
    try:
        rows = client.read_all_values(WORKSHEET_TITLE)
    except Exception:
        logger.info("Substitutions tab not found — using code defaults")
        return list(ACTIVE_SUBSTITUTIONS)

    if len(rows) <= 1:
        logger.info("Substitutions tab empty — using code defaults")
        return list(ACTIVE_SUBSTITUTIONS)

    subs: list[DriverSubstitution] = []
    for row in rows[1:]:
        if len(row) < 3 or not row[0].strip():
            continue
        try:
            rounds = [int(r.strip()) for r in row[2].split(",") if r.strip()]
        except ValueError:
            logger.warning(f"Invalid rounds value in Substitutions tab: {row[2]}")
            continue
        reason = row[3].strip() if len(row) > 3 else ""
        active_str = row[4].strip().upper() if len(row) > 4 else "TRUE"
        active = active_str not in ("FALSE", "0", "NO")
        subs.append(DriverSubstitution(
            original_driver=row[0].strip(),
            substitute_driver=row[1].strip(),
            rounds=rounds,
            reason=reason,
            active=active,
        ))
    logger.info(f"Loaded {len(subs)} substitutions from sheet")
    return subs


def write_substitutions(
    client: SheetsClient,
    substitutions: list[DriverSubstitution],
) -> None:
    """Write substitutions to the sheet (creates tab if needed)."""
    rows = [["Original Driver", "Substitute Driver", "Rounds", "Reason", "Active"]]
    for s in substitutions:
        rows.append([
            s.original_driver,
            s.substitute_driver,
            ", ".join(str(r) for r in s.rounds),
            s.reason,
            "TRUE" if s.active else "FALSE",
        ])
    client.write_all_values(WORKSHEET_TITLE, rows)
    logger.info(f"Wrote {len(substitutions)} substitutions to sheet")
