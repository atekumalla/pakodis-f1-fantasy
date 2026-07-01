"""Scoring Rules sheet — writes the rules to a reference tab in Google Sheets."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.scoring.rules import ScoringRules, DEFAULT_RULES

if TYPE_CHECKING:
    from src.sheets.client import SheetsClient

logger = logging.getLogger(__name__)

WORKSHEET_TITLE = "Scoring Rules"


def write_scoring_rules(client: SheetsClient, rules: ScoringRules | None = None):
    """Write scoring rules to a reference tab."""
    rules = rules or DEFAULT_RULES

    rows = [
        ["Session Type", "Position", "Points", "Notes"],
        [],
        ["QUALIFYING (Top 10)", "", "", ""],
    ]

    for pos, pts in sorted(rules.qualifying_points.items()):
        rows.append(["", f"P{pos}", pts, ""])

    rows.append([])
    rows.append(["FEATURE RACE (Top 15)", "", "", ""])

    for pos, pts in sorted(rules.race_points.items()):
        rows.append(["", f"P{pos}", pts, ""])

    rows.append([])
    rows.append(["SPRINT RACE (Top 10)", "", "", "Not every GP has a sprint"])

    for pos, pts in sorted(rules.sprint_points.items()):
        rows.append(["", f"P{pos}", pts, ""])

    rows.append([])
    rows.append(["IMPORTANT NOTES", "", "", ""])
    rows.append(["", "DNF / DNS / DSQ", "0", "No points for non-finishers"])
    rows.append(["", "P11+ (Qualifying)", "0", "Only top 10 score in qualifying"])
    rows.append(["", "P16+ (Race)", "0", "Only top 15 score in race"])
    rows.append(["", "P11+ (Sprint)", "0", "Only top 10 score in sprint"])
    rows.append([])
    rows.append(["SEASON STRUCTURE", "", "", ""])
    rows.append(["", "H1: Rounds 1-12", "", "First-half draft picks"])
    rows.append(["", "H2: Rounds 13-24", "", "Second-half draft picks (after mid-season redraft)"])
    rows.append(["", "Halfway Point", "", "British GP (Round 12)"])

    client.write_all_values(WORKSHEET_TITLE, rows)
    logger.info("Wrote scoring rules to sheet")
