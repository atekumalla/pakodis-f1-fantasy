"""Draft Pick model — maps a fantasy player to a drafted F1 driver."""

from __future__ import annotations

from pydantic import BaseModel


class DraftPick(BaseModel):
    """Maps a fantasy player to a drafted F1 driver."""

    player_name: str
    driver_name: str
    pick_order: int = 0
    half: str = "H1"          # "H1" or "H2"
