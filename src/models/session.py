"""F1 Session models — Qualifying, Sprint, Race."""

from __future__ import annotations

from datetime import date as _date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SessionType(str, Enum):
    QUALIFYING = "qualifying"
    SPRINT = "sprint"
    RACE = "race"


class SessionStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class SessionResult(BaseModel):
    """A single driver's result in a session."""

    driver_number: int
    driver_name: str = ""
    position: Optional[int] = None      # Final position (None if DNF/DNS)
    dnf: bool = False
    dns: bool = False
    dsq: bool = False
    points_earned: float = 0.0          # Calculated fantasy points

    @property
    def is_classified(self) -> bool:
        """Whether the driver finished and has a valid position."""
        return self.position is not None and not self.dnf and not self.dns and not self.dsq


class Session(BaseModel):
    """A single scored session (Qualifying, Sprint, or Race)."""

    session_key: int                    # OpenF1 unique ID
    meeting_key: int                    # Parent GP weekend
    session_type: SessionType
    session_name: str                   # e.g. "Race", "Qualifying"
    grand_prix: str                     # e.g. "British Grand Prix"
    round_number: int = 0              # Race weekend number (1-24)
    circuit: str = ""                   # e.g. "Silverstone"
    country: str = ""
    session_date: _date = Field(default_factory=_date.today)
    status: SessionStatus = SessionStatus.SCHEDULED
    results: list[SessionResult] = Field(default_factory=list)

    @property
    def is_finished(self) -> bool:
        return self.status == SessionStatus.FINISHED

    @property
    def is_live(self) -> bool:
        return self.status == SessionStatus.IN_PROGRESS

    @property
    def is_h1(self) -> bool:
        """Whether this session belongs to the first half (Rounds 1-12)."""
        from src.config import HALFWAY_ROUND
        return self.round_number <= HALFWAY_ROUND

    @property
    def half(self) -> str:
        """Return 'H1' or 'H2'."""
        return "H1" if self.is_h1 else "H2"


class RaceWeekend(BaseModel):
    """A Grand Prix weekend containing multiple sessions."""

    meeting_key: int
    round_number: int
    name: str                           # e.g. "British Grand Prix"
    circuit: str
    country: str
    race_date: _date
    has_sprint: bool = False
    is_cancelled: bool = False          # True if the race was canceled
    status: str = "scheduled"           # scheduled / finished / cancelled
    sessions: list[Session] = Field(default_factory=list)
