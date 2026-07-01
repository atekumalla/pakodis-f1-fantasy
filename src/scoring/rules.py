"""Scoring rules for the F1 2026 Fantasy Draft.

Points Systems:
  Qualifying (Top 10):  P1=10, P2=9, ... P10=1
  Feature Race (Top 15): P1=50, P2=40, P3=35, P4=30, P5=25, P6=20,
                          P7=18, P8=16, P9=14, P10=12, P11=10, P12=9,
                          P13=8, P14=7, P15=5
  Sprint Race (Top 10):  P1=10, P2=9, ... P10=1
  DNF / DNS / DSQ:       0 points
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.session import SessionType


@dataclass(frozen=True)
class ScoringRules:
    """Immutable scoring rules configuration."""

    qualifying_points: dict[int, int] = field(default_factory=lambda: {
        1: 10, 2: 9, 3: 8, 4: 7, 5: 6,
        6: 5, 7: 4, 8: 3, 9: 2, 10: 1,
    })

    race_points: dict[int, int] = field(default_factory=lambda: {
        1: 50, 2: 40, 3: 35, 4: 30, 5: 25,
        6: 20, 7: 18, 8: 16, 9: 14, 10: 12,
        11: 10, 12: 9, 13: 8, 14: 7, 15: 5,
    })

    sprint_points: dict[int, int] = field(default_factory=lambda: {
        1: 10, 2: 9, 3: 8, 4: 7, 5: 6,
        6: 5, 7: 4, 8: 3, 9: 2, 10: 1,
    })

    def get_points(self, session_type: SessionType, position: int) -> int:
        """Look up points for a position in a given session type."""
        table = {
            SessionType.QUALIFYING: self.qualifying_points,
            SessionType.RACE: self.race_points,
            SessionType.SPRINT: self.sprint_points,
        }[session_type]
        return table.get(position, 0)

    def get_table(self, session_type: SessionType) -> dict[int, int]:
        """Get the full points table for a session type."""
        return {
            SessionType.QUALIFYING: self.qualifying_points,
            SessionType.RACE: self.race_points,
            SessionType.SPRINT: self.sprint_points,
        }[session_type]

    def to_dict(self) -> dict:
        return {
            "qualifying": {f"P{k}": v for k, v in sorted(self.qualifying_points.items())},
            "race": {f"P{k}": v for k, v in sorted(self.race_points.items())},
            "sprint": {f"P{k}": v for k, v in sorted(self.sprint_points.items())},
            "notes": [
                "Qualifying: Top 10 score (P1=10 down to P10=1)",
                "Feature Race: Top 15 score (P1=50 down to P15=5)",
                "Sprint Race: Top 10 score (P1=10 down to P10=1), not every GP",
                "DNF / DNS / DSQ = 0 points",
            ],
        }


DEFAULT_RULES = ScoringRules()
