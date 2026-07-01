"""Draft Picks sheet — manages 'Draft Picks H1' and 'Draft Picks H2' tabs.

Sheet layout (same for both):
  | Player | Driver 1 | Driver 2 | Driver 3 | Driver 4 | Driver 5 |
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.models.player import DraftPlayer

if TYPE_CHECKING:
    from src.sheets.client import SheetsClient

logger = logging.getLogger(__name__)

WORKSHEET_H1 = "Draft Picks H1"
WORKSHEET_H2 = "Draft Picks H2"


def read_draft_picks(client: SheetsClient) -> list[DraftPlayer]:
    """Read draft picks from both H1 and H2 tabs, returning merged DraftPlayer objects."""
    players_map: dict[str, DraftPlayer] = {}

    # Read H1
    _read_half(client, WORKSHEET_H1, players_map, half="H1")
    # Read H2 (may not exist yet)
    _read_half(client, WORKSHEET_H2, players_map, half="H2")

    players = list(players_map.values())
    logger.info(f"Loaded {len(players)} draft players from sheets")
    return players


def _read_half(
    client: SheetsClient,
    worksheet_title: str,
    players_map: dict[str, DraftPlayer],
    half: str,
):
    """Read a single half's draft picks tab."""
    try:
        data = client.read_all_values(worksheet_title)
    except Exception:
        logger.debug(f"No {worksheet_title} tab found (not created yet)")
        return

    if not data or len(data) < 2:
        return

    for row in data[1:]:  # Skip header
        if not row or not row[0].strip():
            continue
        name = row[0].strip()
        drivers = [cell.strip() for cell in row[1:] if cell.strip()]

        if name not in players_map:
            players_map[name] = DraftPlayer(name=name)

        if half == "H1":
            players_map[name].drivers_h1 = drivers
        else:
            players_map[name].drivers_h2 = drivers


def write_draft_picks_h1(client: SheetsClient, players: list[DraftPlayer]):
    """Write H1 draft picks to the Google Sheet."""
    _write_half(client, WORKSHEET_H1, players, half="H1")


def write_draft_picks_h2(client: SheetsClient, players: list[DraftPlayer]):
    """Write H2 draft picks to the Google Sheet."""
    _write_half(client, WORKSHEET_H2, players, half="H2")


def _write_half(
    client: SheetsClient,
    worksheet_title: str,
    players: list[DraftPlayer],
    half: str,
):
    """Write draft picks for one half."""
    max_drivers = 5
    header = ["Player"] + [f"Driver {i+1}" for i in range(max_drivers)]

    rows = [header]
    for player in players:
        drivers = player.drivers_for_half(half)
        row = [player.name] + drivers + [""] * (max_drivers - len(drivers))
        rows.append(row)

    client.write_all_values(worksheet_title, rows)
    logger.info(f"Wrote {len(players)} players to '{worksheet_title}'")
