"""Scoring calculator — computes fantasy points from session results."""

from __future__ import annotations

import logging

from src.models.session import Session, SessionResult, SessionStatus
from src.models.player import DraftPlayer
from src.scoring.rules import ScoringRules, DEFAULT_RULES

logger = logging.getLogger(__name__)

# Map alternative names → canonical name (all lowercase)
# Draft picks may use short names while OpenF1 API uses full legal names
_NAME_ALIASES: dict[str, str] = {
    "alex albon": "alexander albon",
}


def normalize_driver_name(name: str) -> str:
    """Normalize a driver name for consistent matching.
    
    Handles case differences and known aliases (e.g. Alex → Alexander).
    """
    lower = name.lower()
    return _NAME_ALIASES.get(lower, lower)



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
        substitutions: list | None = None,
    ) -> float:
        """Points for a single player in a single session, using correct half ownership."""
        from src.substitutions import get_effective_drivers
        half = session.half
        drivers = player.drivers_for_half(half)
        drivers = get_effective_drivers(drivers, session.round_number, substitutions)
        pts_map = self.calculate_session_points(session)
        
        # Build normalized lookup for driver name matching
        pts_map_norm = {normalize_driver_name(k): v for k, v in pts_map.items()}
        return sum(pts_map_norm.get(normalize_driver_name(d), 0.0) for d in drivers)

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
        driver_norm = normalize_driver_name(driver_name)
        for session in sessions:
            if half and session.half != half:
                continue
            pts_map = self.calculate_session_points(session)
            pts_map_norm = {normalize_driver_name(k): v for k, v in pts_map.items()}
            total += pts_map_norm.get(driver_norm, 0.0)
        return round(total, 2)

    def calculate_driver_breakdown(
        self,
        driver_name: str,
        sessions: list[Session],
        half: str | None = None,
    ) -> dict[str, float]:
        """Points breakdown by session type (race, qualifying, sprint)."""
        breakdown = {"race": 0.0, "qualifying": 0.0, "sprint": 0.0}
        driver_norm = normalize_driver_name(driver_name)
        for session in sessions:
            if half and session.half != half:
                continue
            pts_map = self.calculate_session_points(session)
            pts_map_norm = {normalize_driver_name(k): v for k, v in pts_map.items()}
            pts = pts_map_norm.get(driver_norm, 0.0)
            if pts > 0:
                breakdown[session.session_type.value] = round(
                    breakdown.get(session.session_type.value, 0.0) + pts, 2
                )
        return breakdown

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
        from src.seed_data import DRIVERS_2026, SUBSTITUTE_DRIVERS, TEAM_COLORS, COUNTRY_FLAGS
        from src.substitutions import get_substitute_for_round, get_all_substitution_info
        
        # Build a lookup for driver details (grid + substitutes)
        driver_info = {}
        for d in DRIVERS_2026 + SUBSTITUTE_DRIVERS:
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

        # Collect active substitution info
        active_subs = get_all_substitution_info()

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
            sub_drivers_h2 = []
            for d in player.drivers_h2:
                # Points for this driver excluding substitution rounds
                pts = 0.0
                sub_rounds_for_driver: dict[str, list[int]] = {}
                for s in finished:
                    if s.half != "H2":
                        continue
                    sub_name = get_substitute_for_round(d, s.round_number)
                    if sub_name:
                        sub_rounds_for_driver.setdefault(sub_name, []).append(s.round_number)
                    else:
                        pts_map = self.calculate_session_points(s)
                        pts_map_norm = {normalize_driver_name(k): v for k, v in pts_map.items()}
                        pts += pts_map_norm.get(normalize_driver_name(d), 0.0)
                pts = round(pts, 2)

                info = driver_info.get(d, {})
                entry = {"name": d, "points": pts, **info}
                if sub_rounds_for_driver:
                    entry["has_substitutions"] = True
                    entry["substitution_rounds"] = {}
                    for sn, rnds in sub_rounds_for_driver.items():
                        entry["substitution_rounds"][sn] = rnds
                drivers_h2.append(entry)

                # Build separate sub driver entries
                for sub_name, sub_rnds in sub_rounds_for_driver.items():
                    sub_pts = 0.0
                    for s in finished:
                        if s.half != "H2" or s.round_number not in sub_rnds:
                            continue
                        pts_map = self.calculate_session_points(s)
                        pts_map_norm = {normalize_driver_name(k): v for k, v in pts_map.items()}
                        sub_pts += pts_map_norm.get(normalize_driver_name(sub_name), 0.0)
                    sub_pts = round(sub_pts, 2)
                    sub_info = driver_info.get(sub_name, {})
                    sub_drivers_h2.append({
                        "name": sub_name,
                        "points": sub_pts,
                        "substitute_for": d,
                        "substitute_rounds": sub_rnds,
                        "is_substitute": True,
                        **sub_info,
                    })

            drivers_h2.sort(key=lambda x: x["points"], reverse=True)
            sub_drivers_h2.sort(key=lambda x: x["points"], reverse=True)
            drivers_h2.extend(sub_drivers_h2)

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
