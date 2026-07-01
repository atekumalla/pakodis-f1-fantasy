"""OpenF1 API client — fetches live and historical F1 session data.

Endpoints used (https://api.openf1.org/v1/):
  GET /meetings?year=YYYY         — All GP weekends in a season
  GET /sessions?meeting_key=X     — Sessions for a GP weekend
  GET /drivers?session_key=X      — Driver info for a session
  GET /position?session_key=X     — Position data (used for results)

Free tier: 3 req/s, 30 req/min. No authentication needed.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Optional

import requests

from src.config import Config
from src.models.driver import Driver
from src.models.session import (
    Session,
    SessionResult,
    SessionStatus,
    SessionType,
    RaceWeekend,
)
from src.utils.retry import api_retry

logger = logging.getLogger(__name__)

# Map OpenF1 session_name → our SessionType (only these earn points)
SESSION_TYPE_MAP = {
    "Qualifying": SessionType.QUALIFYING,
    "Sprint": SessionType.SPRINT,
    "Race": SessionType.RACE,
}

# Session names we ignore (no points)
IGNORED_SESSIONS = {"Practice 1", "Practice 2", "Practice 3", "Sprint Qualifying", "Sprint Shootout"}


class OpenF1API:
    """Client for the OpenF1 REST API."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or Config.OPENF1_BASE_URL).rstrip("/")
        self._driver_cache: dict[int, Driver] = {}
        self._last_request_time: float = 0
        self._min_interval: float = 2.1  # ~28 req/min (API limit is 30 req/min)

    def _rate_limit(self):
        """Ensure we don't exceed API rate limits (30 req/min)."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _get(self, endpoint: str, params: dict | None = None) -> list[dict]:
        """Make a GET request to the OpenF1 API with 429 backoff."""
        max_retries = 3
        for attempt in range(max_retries):
            self._rate_limit()
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            logger.debug(f"GET {url} params={params}")
            try:
                resp = requests.get(url, params=params, timeout=30)
                
                # Handle 429 rate limit with increasing backoff
                if resp.status_code == 429:
                    backoff = (attempt + 1) * 30  # 30s, 60s, 90s
                    logger.warning(
                        f"Rate limited (429) on {endpoint}, "
                        f"backing off {backoff}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(backoff)
                    continue
                    
                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, list) else [data]
            except requests.exceptions.RequestException as e:
                logger.warning(f"API request failed for {endpoint}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return []
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse API response for {endpoint}: {e}")
                return []
        return []

    # ── High-level methods ────────────────────────────────────────────

    def fetch_season_meetings(
        self, year: int | None = None, include_testing: bool = False
    ) -> list[dict]:
        """Fetch all GP weekends for a season.
        
        Args:
            year: Season year (defaults to Config.F1_SEASON_YEAR)
            include_testing: If True, include pre-season testing events
            
        Returns:
            List of meeting dicts. Each meeting has an 'is_cancelled' field.
        """
        year = year or Config.F1_SEASON_YEAR
        meetings = self._get("meetings", {"year": year})
        
        # Filter out pre-season testing events unless requested
        if not include_testing:
            meetings = [
                m for m in meetings
                if "testing" not in m.get("meeting_name", "").lower()
            ]
        
        # Log summary
        total = len(meetings)
        canceled = sum(1 for m in meetings if m.get("is_cancelled", False))
        active = total - canceled
        logger.info(
            f"Fetched {total} meetings for {year} "
            f"({active} active, {canceled} canceled)"
        )
        return meetings

    def fetch_sessions(self, meeting_key: int) -> list[dict]:
        """Fetch all sessions for a GP weekend."""
        return self._get("sessions", {"meeting_key": meeting_key})

    def fetch_drivers(self, session_key: int) -> list[Driver]:
        """Fetch driver info for a session and cache it."""
        raw = self._get("drivers", {"session_key": session_key})
        drivers = []
        seen = set()
        for d in raw:
            num = d.get("driver_number")
            if num is None or num in seen:
                continue
            seen.add(num)
            driver = Driver(
                driver_number=num,
                full_name=d.get("full_name", f"Driver #{num}"),
                name_acronym=d.get("name_acronym", ""),
                team_name=d.get("team_name", ""),
                headshot_url=d.get("headshot_url"),
            )
            drivers.append(driver)
            self._driver_cache[num] = driver
        return drivers

    def fetch_positions(self, session_key: int) -> list[dict]:
        """Fetch position data for a session."""
        return self._get("position", {"session_key": session_key})

    def get_session_results(self, session_key: int) -> list[SessionResult]:
        """
        Derive final results from position data.

        Strategy: for each driver, take their last recorded position entry
        (the most recent timestamp) as their finishing position.
        
        Returns empty list if no data available (e.g., canceled race).
        """
        try:
            positions = self.fetch_positions(session_key)
        except Exception as e:
            logger.warning(f"Failed to fetch positions for session {session_key}: {e}")
            return []
            
        if not positions:
            logger.info(f"No position data for session {session_key} (may be canceled or not yet run)")
            return []

        # Ensure we have driver names cached
        if not self._driver_cache:
            try:
                self.fetch_drivers(session_key)
            except Exception as e:
                logger.warning(f"Failed to fetch drivers for session {session_key}: {e}")

        # Group by driver_number, keep the latest entry for each
        latest: dict[int, dict] = {}
        for p in positions:
            num = p.get("driver_number")
            if num is None:
                continue
            ts = p.get("date", "")
            if num not in latest or ts > latest[num].get("date", ""):
                latest[num] = p

        results = []
        for num, p in latest.items():
            driver = self._driver_cache.get(num)
            name = driver.full_name if driver else f"Driver #{num}"
            pos = p.get("position")
            results.append(SessionResult(
                driver_number=num,
                driver_name=name,
                position=pos,
                dnf=False,
                dns=False,
                dsq=False,
            ))

        results.sort(key=lambda r: r.position if r.position else 99)
        return results

    def fetch_all_scored_sessions(
        self, year: int | None = None
    ) -> list[Session]:
        """
        Fetch all scored sessions (Qualifying, Sprint, Race) for the season.

        This is the main entry point for syncing.
        Handles canceled races gracefully by skipping them (0 points for all).
        """
        year = year or Config.F1_SEASON_YEAR
        meetings = self.fetch_season_meetings(year)
        
        if not meetings:
            logger.warning(f"No meetings found for {year}")
            return []

        all_sessions: list[Session] = []
        round_number = 0  # Track actual round number (excluding canceled)

        for meeting in meetings:
            meeting_key = meeting.get("meeting_key")
            gp_name = meeting.get("meeting_name", f"GP")
            circuit = meeting.get("circuit_short_name", "")
            country = meeting.get("country_name", "")
            is_cancelled = meeting.get("is_cancelled", False)

            if not meeting_key:
                logger.warning(f"Skipping meeting with no key: {gp_name}")
                continue

            # Skip canceled races entirely (everyone gets 0 points)
            if is_cancelled:
                logger.info(f"Skipping canceled race: {gp_name}")
                continue
            
            round_number += 1

            try:
                raw_sessions = self.fetch_sessions(meeting_key)
            except Exception as e:
                logger.warning(f"Failed to fetch sessions for {gp_name}: {e}")
                raw_sessions = []
            
            if not raw_sessions:
                logger.info(f"No session data for {gp_name} (may not yet be scheduled)")
                continue

            for raw in raw_sessions:
                session_name = raw.get("session_name", "")
                session_type = SESSION_TYPE_MAP.get(session_name)

                if session_type is None:
                    continue  # Skip practice, sprint quali, etc.

                session_key = raw.get("session_key")
                if not session_key:
                    continue

                # Determine status
                date_start = raw.get("date_start", "")
                date_end = raw.get("date_end", "")
                status = self._determine_status(date_start, date_end)

                # Parse date
                session_date = date.today()
                if date_start:
                    try:
                        session_date = datetime.fromisoformat(
                            date_start.replace("Z", "+00:00")
                        ).date()
                    except (ValueError, TypeError):
                        pass

                # Fetch results if session is finished
                # Empty results = 0 points for all drivers (handles canceled sessions)
                results = []
                if status == SessionStatus.FINISHED:
                    try:
                        # Ensure driver cache is populated
                        if not self._driver_cache:
                            self.fetch_drivers(session_key)
                        results = self.get_session_results(session_key)
                        if not results:
                            logger.info(
                                f"No results for {gp_name} {session_name} "
                                "(session may have been canceled — scoring 0 points)"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch results for {gp_name} {session_name}: {e} "
                            "(scoring 0 points)"
                        )

                session = Session(
                    session_key=session_key,
                    meeting_key=meeting_key,
                    session_type=session_type,
                    session_name=session_name,
                    grand_prix=gp_name,
                    round_number=round_number,
                    circuit=circuit,
                    country=country,
                    session_date=session_date,
                    status=status,
                    results=results,
                )
                all_sessions.append(session)

        logger.info(
            f"Fetched {len(all_sessions)} scored sessions for {year} ({round_number} active rounds)"
        )
        return all_sessions

    def fetch_new_sessions(
        self, 
        year: int | None = None,
        exclude_keys: set[int] | None = None,
        exclude_identities: set[tuple] | None = None,
    ) -> list[Session]:
        """
        Fetch only NEW sessions that aren't already known.
        
        This is an optimized version of fetch_all_scored_sessions that:
        1. Skips sessions we already have (by session_key OR round+type identity)
        2. Only fetches results for new finished sessions
        3. Minimizes API calls
        
        Args:
            year: Season year
            exclude_keys: Set of session_keys to skip (already have data for)
            exclude_identities: Set of (round_number, session_type_value) tuples to skip.
                This handles the case where sessions loaded from sheets have synthetic keys
                that don't match real API keys.
            
        Returns:
            List of new Session objects only
        """
        year = year or Config.F1_SEASON_YEAR
        exclude_keys = exclude_keys or set()
        exclude_identities = exclude_identities or set()
        
        meetings = self.fetch_season_meetings(year)
        
        if not meetings:
            logger.warning(f"No meetings found for {year}")
            return []

        new_sessions: list[Session] = []
        round_number = 0

        for meeting in meetings:
            meeting_key = meeting.get("meeting_key")
            gp_name = meeting.get("meeting_name", "GP")
            circuit = meeting.get("circuit_short_name", "")
            country = meeting.get("country_name", "")
            is_cancelled = meeting.get("is_cancelled", False)

            if not meeting_key:
                continue

            if is_cancelled:
                logger.info(f"Skipping canceled race: {gp_name}")
                continue
            
            round_number += 1
            
            # Quick check: if we already have qualifying + race for this round,
            # skip the entire meeting (saves an API call)
            known_types_for_round = {
                st for (rn, st) in exclude_identities if rn == round_number
            }
            if "qualifying" in known_types_for_round and "race" in known_types_for_round:
                logger.debug(f"Skipping {gp_name} — already have qualifying + race")
                continue

            try:
                raw_sessions = self.fetch_sessions(meeting_key)
            except Exception as e:
                logger.warning(f"Failed to fetch sessions for {gp_name}: {e}")
                continue
            
            if not raw_sessions:
                continue

            for raw in raw_sessions:
                session_name = raw.get("session_name", "")
                session_type = SESSION_TYPE_MAP.get(session_name)

                if session_type is None:
                    continue  # Skip practice, sprint quali, etc.

                session_key = raw.get("session_key")
                if not session_key:
                    continue
                    
                # Skip if we already have this session (by real API key)
                if session_key in exclude_keys:
                    continue
                
                # Skip if we already have this session (by round+type identity)
                # This catches sessions loaded from sheets with synthetic keys
                if (round_number, session_type.value) in exclude_identities:
                    continue

                # Determine status
                date_start = raw.get("date_start", "")
                date_end = raw.get("date_end", "")
                status = self._determine_status(date_start, date_end)
                
                # Only fetch results for FINISHED sessions
                if status != SessionStatus.FINISHED:
                    continue

                # Parse date
                session_date = date.today()
                if date_start:
                    try:
                        session_date = datetime.fromisoformat(
                            date_start.replace("Z", "+00:00")
                        ).date()
                    except (ValueError, TypeError):
                        pass

                # Fetch results
                results = []
                try:
                    if not self._driver_cache:
                        self.fetch_drivers(session_key)
                    results = self.get_session_results(session_key)
                except Exception as e:
                    logger.warning(f"Failed to fetch results for {gp_name} {session_name}: {e}")

                if not results:
                    logger.info(f"No results for {gp_name} {session_name} (skipping)")
                    continue

                session = Session(
                    session_key=session_key,
                    meeting_key=meeting_key,
                    session_type=session_type,
                    session_name=session_name,
                    grand_prix=gp_name,
                    round_number=round_number,
                    circuit=circuit,
                    country=country,
                    session_date=session_date,
                    status=status,
                    results=results,
                )
                new_sessions.append(session)
                logger.info(f"Found new session: {gp_name} {session_name}")

        logger.info(f"Found {len(new_sessions)} new sessions to sync")
        return new_sessions

    def fetch_race_calendar(
        self, year: int | None = None, include_cancelled: bool = True
    ) -> list[RaceWeekend]:
        """Fetch the race calendar as RaceWeekend objects.
        
        Args:
            year: Season year (defaults to Config.F1_SEASON_YEAR)
            include_cancelled: If True, include canceled races in the calendar
            
        Returns:
            List of RaceWeekend objects with proper round numbers.
            Canceled races are marked with is_cancelled=True.
        """
        year = year or Config.F1_SEASON_YEAR
        meetings = self.fetch_season_meetings(year)
        
        if not meetings:
            logger.warning(f"No meetings found for {year}")
            return []

        weekends = []
        round_number = 0  # Track actual round number (excluding canceled)
        
        for m in meetings:
            meeting_key = m.get("meeting_key")
            gp_name = m.get("meeting_name", "Grand Prix")
            is_cancelled = m.get("is_cancelled", False)
            
            if not meeting_key:
                logger.warning(f"Skipping meeting with no key: {gp_name}")
                continue

            # Only increment round number for non-canceled races
            if not is_cancelled:
                round_number += 1
            
            # Skip canceled races if not wanted
            if is_cancelled and not include_cancelled:
                continue

            # Try to fetch sessions, but don't fail if unavailable
            has_sprint = False
            if not is_cancelled:
                try:
                    raw_sessions = self.fetch_sessions(meeting_key)
                    if raw_sessions:
                        has_sprint = any(
                            s.get("session_name") in ("Sprint", "Sprint Shootout")
                            for s in raw_sessions
                        )
                except Exception as e:
                    logger.warning(f"Could not fetch sessions for {gp_name}: {e}")

            # Parse date
            d = date.today()
            date_start = m.get("date_start", "")
            if date_start:
                try:
                    d = datetime.fromisoformat(
                        date_start.replace("Z", "+00:00")
                    ).date()
                except (ValueError, TypeError):
                    pass

            weekend = RaceWeekend(
                meeting_key=meeting_key,
                round_number=round_number if not is_cancelled else 0,
                name=gp_name,
                circuit=m.get("circuit_short_name", ""),
                country=m.get("country_name", ""),
                race_date=d,
                has_sprint=has_sprint,
                is_cancelled=is_cancelled,
                status="cancelled" if is_cancelled else "scheduled",
            )
            weekends.append(weekend)

        active_count = sum(1 for w in weekends if not w.is_cancelled)
        logger.info(f"Built race calendar: {active_count} active races for {year}")
        return weekends

    def get_season_stats(self, year: int | None = None) -> dict:
        """Get stats about the season (total races, canceled, halfway point, etc.)
        
        Returns:
            Dict with keys: total_races, canceled_races, active_races, halfway_round
        """
        year = year or Config.F1_SEASON_YEAR
        meetings = self.fetch_season_meetings(year)
        
        total = len(meetings)
        canceled = sum(1 for m in meetings if m.get("is_cancelled", False))
        active = total - canceled
        halfway = active // 2  # Halfway is at half the active races
        
        return {
            "total_races": total,
            "canceled_races": canceled,
            "active_races": active,
            "halfway_round": halfway,
        }

    # ── Helpers ───────────────────────────────────────────────────────

    def _determine_status(
        self, date_start: str, date_end: str
    ) -> SessionStatus:
        """Determine session status from start/end timestamps."""
        if not date_start:
            return SessionStatus.SCHEDULED

        try:
            start = datetime.fromisoformat(date_start.replace("Z", "+00:00"))
            now = datetime.now(start.tzinfo)

            if date_end:
                end = datetime.fromisoformat(date_end.replace("Z", "+00:00"))
                if now > end:
                    return SessionStatus.FINISHED
                elif now >= start:
                    return SessionStatus.IN_PROGRESS
            else:
                # No end time — estimate: qualifying ~1hr, race ~2hr, sprint ~30min
                if now > start:
                    return SessionStatus.FINISHED
        except (ValueError, TypeError):
            pass

        return SessionStatus.SCHEDULED

    def get_driver_name(self, driver_number: int) -> str:
        """Look up a driver name from cache."""
        driver = self._driver_cache.get(driver_number)
        return driver.full_name if driver else f"Driver #{driver_number}"
