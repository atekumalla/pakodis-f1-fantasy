"""Scoring calculator — computes fantasy points from session results."""

from __future__ import annotations

import logging

from src.models.session import Session, SessionResult, SessionStatus
from src.models.player import DraftPlayer
from src.scoring.rules import ScoringRules, DEFAULT_RULES

logger = logging.getLogger(__name__)


class ScoringCalculator:
    """Calculates fantasy draft points for F1 session results."""

    def __init__(self, rules: ScoringRules | None = None):
        self.rules = rules or DEFAULT_RULES

    def calculate_session_points(self, session: Session) -> dict[str, float]:
        """
        Calculate fantasy points for all drivers in a session.

        Returns:
            Dict mapping driver_name -> points earned in this session.
            Empty dict if session hasn't finished.
        """
        if session.status not in (SessionStatus.FINISHED, SessionStatus.IN_PROGRESS):
            return {}

        points_map: dict[str, float] = {}
        for result in session.results:
            if not result.is_classified or result.position is None:
                points_map[result.driver_name] = 0.0
            else:
                pts = self.rules.get_points(session.session_type, result.position)
                points_map[result.driver_name] = float(pts)
                result.points_earned = float(pts)

        return points_map

    def calculate_player_session_points(
        self,
        player: DraftPlayer,
        session: Session,
    ) -> float:
        """Points for a single player in a single session, using correct half ownership."""
        half = session.half
        drivers = player.drivers_for_half(half)
        pts_map = self.calculate_session_points(session)
        
        # Build case-insensitive lookup for driver name matching
        pts_map_lower = {k.lower(): v for k, v in pts_map.items()}
        return sum(pts_map_lower.get(d.lower(), 0.0) for d in drivers)

    def calculate_player_total(
        self,
        player: DraftPlayer,
        sessions: list[Session],
        half: str | None = None,
    ) -> float:
        """
        Total points for a fantasy player across sessions.

        Args:
            player: The draft player
            sessions: All scored sessions
            half: If set ('H1' or 'H2'), only count sessions in that half.
                  If None, count all sessions using correct half ownership.
        """
        total = 0.0
        for session in sessions:
            if half and session.half != half:
                continue
            total += self.calculate_player_session_points(player, session)
        return round(total, 2)

    def calculate_driver_total(
        self,
        driver_name: str,
        sessions: list[Session],
        half: str | None = None,
    ) -> float:
        """Total points a specific driver earned across sessions."""
        total = 0.0
        driver_lower = driver_name.lower()
        for session in sessions:
            if half and session.half != half:
                continue
            pts_map = self.calculate_session_points(session)
            pts_map_lower = {k.lower(): v for k, v in pts_map.items()}
            total += pts_map_lower.get(driver_lower, 0.0)
        return round(total, 2)

    def build_leaderboard(
        self,
        players: list[DraftPlayer],
        sessions: list[Session],
    ) -> list[dict]:
        """
        Build a sorted leaderboard.

        Returns list of dicts: [
            {"name": "Abhinav", "total": 342.0, "h1": 200.0, "h2": 142.0,
             "drivers_h1": [{"name": "Leclerc", "points": 120.0, ...}, ...],
             "drivers_h2": [...]},
            ...
        ]
        """
        from src.seed_data import DRIVERS_2026, TEAM_COLORS, COUNTRY_FLAGS
        
        # Build a lookup for driver details
        driver_info = {}
        for d in DRIVERS_2026:
            driver_info[d["name"]] = {
                "number": d["number"],
                "team": d["team"],
                "acronym": d["acronym"],
                "country": d.get("country", ""),
                "country_flag": COUNTRY_FLAGS.get(d.get("country", ""), ""),
                "team_color": TEAM_COLORS.get(d["team"], "888888"),
                "headshot_url": d.get("headshot_url", ""),
            }
        
        # Pre-compute driver points per half
        finished = [s for s in sessions if s.is_finished or s.is_live]

        leaderboard = []
        for player in players:
            h1_total = self.calculate_player_total(player, finished, half="H1")
            h2_total = self.calculate_player_total(player, finished, half="H2")

            drivers_h1 = []
            for d in player.drivers_h1:
                pts = self.calculate_driver_total(d, finished, half="H1")
                info = driver_info.get(d, {})
                drivers_h1.append({
                    "name": d,
                    "points": pts,
                    **info,
                })
            drivers_h1.sort(key=lambda x: x["points"], reverse=True)

            drivers_h2 = []
            for d in player.drivers_h2:
                pts = self.calculate_driver_total(d, finished, half="H2")
                info = driver_info.get(d, {})
                drivers_h2.append({
                    "name": d,
                    "points": pts,
                    **info,
                })
            drivers_h2.sort(key=lambda x: x["points"], reverse=True)

            leaderboard.append({
                "name": player.name,
                "total": round(h1_total + h2_total, 2),
                "h1": h1_total,
                "h2": h2_total,
                "drivers_h1": drivers_h1,
                "drivers_h2": drivers_h2,
            })

        leaderboard.sort(key=lambda x: x["total"], reverse=True)
        return leaderboard
