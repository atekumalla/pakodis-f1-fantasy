"""Draft Player model — represents one of the 4 friends in the fantasy draft."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DraftPlayer(BaseModel):
    """A person participating in the fantasy draft."""

    name: str                                       # e.g. "Abhinav"
    drivers_h1: list[str] = Field(default_factory=list)   # Driver names for first half
    drivers_h2: list[str] = Field(default_factory=list)   # Driver names for second half (after redraft)

    @property
    def driver_count_h1(self) -> int:
        return len(self.drivers_h1)

    @property
    def driver_count_h2(self) -> int:
        return len(self.drivers_h2)

    def drivers_for_half(self, half: str) -> list[str]:
        """Get driver names for a given half ('H1' or 'H2')."""
        if half == "H2" and self.drivers_h2:
            return self.drivers_h2
        return self.drivers_h1
