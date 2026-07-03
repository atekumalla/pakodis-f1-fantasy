"""Sync ONLY the 'Race Calendar' tab's sprint flags to Google Sheets.

Why this exists
---------------
`python -m src.seed_data` re-seeds the WHOLE spreadsheet — it also rewrites the
H1 draft picks, the scoring rules, and RESETS the leaderboard. That is
destructive to run mid-season.

This script touches only the 'Race Calendar' worksheet. It reads the calendar
that is currently in the sheet, corrects each race's "Has Sprint" value to match
the curated CALENDAR_2026 (the correct 2026 sprint weekends: China, Miami,
Canada, Britain, Netherlands, Singapore), and writes just that one tab back.
Draft picks, the leaderboard, and race results are never touched.

It deliberately does NOT pull the calendar from the OpenF1 API. The API infers
sprint status by probing each meeting's sessions, which is unreliable for races
that have not happened yet (it would report upcoming sprints as regular
weekends). The curated CALENDAR_2026 in the code is the source of truth.

Note: a running server only reads the calendar tab at startup, and the web
dashboard's Upcoming Races table is driven by CALENDAR_2026 in code — so this
change is about making the sheet itself accurate for anyone reading it directly.

Usage
-----
    python sync_calendar_to_sheet.py            # apply the fix
    python sync_calendar_to_sheet.py --dry-run  # preview changes, write nothing
"""

from __future__ import annotations

import argparse
import logging

from src.config import Config
from src.seed_data import CALENDAR_2026
from src.sheets.client import SheetsClient
from src.sheets.schedule import read_calendar, write_calendar
from src.utils.logger import setup_logging

logger = logging.getLogger(__name__)

# Race name -> correct sprint flag, taken from the curated calendar in code.
# (Duplicate names like "Spanish Grand Prix" are all non-sprint, so collapsing
# by name is safe here.)
SPRINT_BY_NAME: dict[str, bool] = {r["name"]: r["sprint"] for r in CALENDAR_2026}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update only the 'Race Calendar' tab's sprint flags to match CALENDAR_2026."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to the sheet.",
    )
    args = parser.parse_args()

    setup_logging()

    errors = Config.validate()
    if errors:
        for err in errors:
            logger.error("Config error: %s", err)
        raise SystemExit(1)

    client = SheetsClient()
    weekends = read_calendar(client)

    if not weekends:
        logger.error(
            "The 'Race Calendar' tab is empty or unreadable. "
            "Run `python -m src.seed_data` first to create the full sheet."
        )
        raise SystemExit(1)

    # Correct the sprint flag on each weekend, tracking what actually changes.
    changes: list[tuple[str, bool, bool]] = []
    for w in weekends:
        correct = SPRINT_BY_NAME.get(w.name)
        if correct is None:
            logger.warning(
                "  ? %s — not found in CALENDAR_2026, leaving as-is (%s)",
                w.name,
                "sprint" if w.has_sprint else "regular",
            )
            continue
        if w.has_sprint != correct:
            changes.append((w.name, w.has_sprint, correct))
            w.has_sprint = correct

    logger.info("Calendar in sheet: %d rounds", len(weekends))
    sprint_names = [w.name for w in weekends if w.has_sprint]
    logger.info(
        "Sprint weekends after fix (%d): %s",
        len(sprint_names),
        ", ".join(sprint_names) or "none",
    )

    if not changes:
        logger.info("Nothing to change — the sheet's sprint flags already match. ✅")
        return

    logger.info("Changes to apply (%d):", len(changes))
    for name, old, new in changes:
        logger.info(
            "  %-28s %s -> %s",
            name,
            "sprint" if old else "regular",
            "sprint" if new else "regular",
        )

    if args.dry_run:
        logger.info("Dry run — no changes written to the sheet.")
        return

    write_calendar(client, weekends)
    logger.info(
        "✅ 'Race Calendar' tab updated. Draft picks, leaderboard, and results untouched."
    )


if __name__ == "__main__":
    main()
