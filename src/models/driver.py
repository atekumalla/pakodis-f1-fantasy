"""F1 Driver model."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class Driver(BaseModel):
    """An F1 driver in the 2026 season."""

    driver_number: int          # e.g. 1, 44, 63
    full_name: str              # e.g. "Max Verstappen"
    name_acronym: str           # e.g. "VER"
    team_name: str              # e.g. "Red Bull Racing"
    headshot_url: Optional[str] = None

    def __hash__(self):
        return hash(self.driver_number)

    def __eq__(self, other):
        if isinstance(other, Driver):
            return self.driver_number == other.driver_number
        return NotImplemented
