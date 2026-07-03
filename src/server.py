"""FastAPI web server — dashboard UI, API endpoints, and mid-season draft system.

Data Architecture:
  - Google Sheets is the SOURCE OF TRUTH for all historical data
  - On startup: Load sessions from sheets (no API calls)
  - During sync: Only fetch NEW sessions from API, then write to sheets
  - Force sync: Re-fetch ALL data from API (use sparingly)

Endpoints:
  GET  /                    → Dashboard HTML
  GET  /draft               → Mid-season draft UI
  GET  /api/status          → Leaderboard, last sync, recent results
  POST /api/sync            → Incremental sync (new sessions only)
  POST /api/sync/force      → Full sync (re-fetch all from API)
  GET  /api/share-text      → Formatted standings for WhatsApp
  GET  /api/drivers         → All 20 drivers with teams
  GET  /api/calendar        → Race calendar with status

  --- Mid-Season Draft ---
  GET  /api/draft/status    → Current draft state
  POST /api/draft/start     → Start draft (randomize or custom order)
  POST /api/draft/pick      → Make a pick
  POST /api/draft/undo      → Undo last pick
  POST /api/draft/reset     → Reset draft
  POST /api/draft/finalize  → Finalize H2 picks to Google Sheets
"""

from __future__ import annotations

import logging
import os
import hmac
from contextlib import asynccontextmanager
from datetime import date as dt_date, timedelta
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import Config, HALFWAY_ROUND
from src.models.session import Session, SessionStatus
from src.models.player import DraftPlayer
from src.scoring.calculator import ScoringCalculator
from src.scoring.rules import DEFAULT_RULES
from src.seed_data import (
    DRIVERS_2026,
    PLAYER_NAMES,
    get_all_driver_names,
    get_initial_players,
)
from src.utils.logger import setup_logging
from src.utils.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

_app_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    setup_logging()

    from src.data_sources.openf1_api import OpenF1API
    from src.sheets.client import SheetsClient
    from src.sheets.players import read_draft_picks
    from src.sheets.schedule import read_calendar
    from src.sync.scheduler import SyncScheduler
    from src.sync.state_manager import StateManager
    from src.draft.manager import DraftManager

    logger.info("Starting F1 2026 Fantasy Draft server...")

    # Separate cooldowns: snappy for the cheap incremental sync, long for the
    # expensive force sync.
    rate_limiter.set_cooldown("sync", Config.SYNC_COOLDOWN_SECONDS)
    rate_limiter.set_cooldown("force_sync", Config.SYNC_FORCE_COOLDOWN_SECONDS)

    state = {
        "sheets_client": None,
        "state_manager": StateManager(),
        "calculator": ScoringCalculator(DEFAULT_RULES),
        "openf1_api": OpenF1API(),
        "draft_manager": DraftManager(all_drivers=get_all_driver_names()),
        "players": get_initial_players(),
        "sessions": [],
        "calendar": [],
    }

    # Try to load from Google Sheets
    has_sheets = bool(Config.GOOGLE_SHEETS_ID) and (
        Config.has_credentials_json()
        or Path(Config.GOOGLE_SHEETS_CREDENTIALS_FILE).exists()
    )

    if has_sheets:
        try:
            from src.sheets.results import read_results
            
            state["sheets_client"] = SheetsClient()
            state["players"] = read_draft_picks(state["sheets_client"])
            state["calendar"] = read_calendar(state["sheets_client"])
            
            # Load historical results from sheets (source of truth)
            state["sessions"] = read_results(state["sheets_client"])
            
            logger.info(
                f"Loaded {len(state['players'])} players, "
                f"{len(state['sessions'])} sessions from sheets"
            )
        except Exception as e:
            logger.warning(f"Failed to load from sheets: {e}")
    else:
        logger.warning("No Google Sheets credentials — running with seed data only")

    def _sync():
        _do_sync(_app_state)

    def _has_live():
        return any(
            s.status == SessionStatus.IN_PROGRESS
            for s in _app_state.get("sessions", [])
        )

    state["scheduler"] = SyncScheduler(
        sync_fn=_sync, has_live_sessions_fn=_has_live
    )

    _app_state.update(state)

    if has_sheets:
        state["scheduler"].start()
        state["scheduler"].trigger_now()

    logger.info("🏎️  Server ready! Open http://localhost:8000")
    yield

    if "scheduler" in state:
        state["scheduler"].stop()
    if state.get("state_manager"):
        state["state_manager"].save()
    logger.info("Server stopped.")


app = FastAPI(title="F1 2026 Fantasy Draft", lifespan=lifespan)

_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# ─── PAGES ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    html_path = _static_dir / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Dashboard not found. Run seed first.</h1>", status_code=404)
    return HTMLResponse(html_path.read_text())


@app.get("/draft", response_class=HTMLResponse)
async def serve_draft_page():
    html_path = _static_dir / "draft.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Draft page not found.</h1>", status_code=404)
    return HTMLResponse(html_path.read_text())


# ─── API: STATUS ─────────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    players = _app_state.get("players", [])
    sessions = _app_state.get("sessions", [])
    calculator: ScoringCalculator = _app_state.get("calculator")
    state_mgr = _app_state.get("state_manager")

    leaderboard = calculator.build_leaderboard(players, sessions)

    # Recent finished sessions
    finished = [s for s in sessions if s.is_finished or s.is_live]
    finished.sort(key=lambda s: s.session_date, reverse=True)

    # Build driver → player map for both halves
    driver_to_player_h1: dict[str, str] = {}
    driver_to_player_h2: dict[str, str] = {}
    for p in players:
        for d in p.drivers_h1:
            driver_to_player_h1[d] = p.name
        for d in p.drivers_h2:
            driver_to_player_h2[d] = p.name

    recent_sessions = []
    for s in finished[:20]:
        pts_map = calculator.calculate_session_points(s)
        # Per-player points for this session
        player_pts = {}
        for p in players:
            pp = calculator.calculate_player_session_points(p, s)
            if pp > 0:
                player_pts[p.name] = round(pp, 2)

        results_list = []
        for r in sorted(s.results, key=lambda x: x.position if x.position else 99):
            owner_map = driver_to_player_h1 if s.is_h1 else driver_to_player_h2
            # Look up owner using normalized name for alias matching
            from src.scoring.calculator import normalize_driver_name
            owner = owner_map.get(r.driver_name)
            if not owner:
                # Try alias matching (e.g. "Alexander ALBON" → "Alex Albon")
                r_norm = normalize_driver_name(r.driver_name)
                for draft_name, player_name in owner_map.items():
                    if normalize_driver_name(draft_name) == r_norm:
                        owner = player_name
                        break
            results_list.append({
                "driver": r.driver_name,
                "driver_number": r.driver_number,
                "position": r.position,
                "points": pts_map.get(r.driver_name, 0),
                "dnf": r.dnf,
                "dns": r.dns,
                "dsq": r.dsq,
                "owner": owner,
            })

        # Get country flag for the race location
        from src.seed_data import RACE_COUNTRY_FLAGS
        country_flag = RACE_COUNTRY_FLAGS.get(s.country, "🏁")

        recent_sessions.append({
            "date": s.session_date.isoformat(),
            "grand_prix": s.grand_prix,
            "country_flag": country_flag,
            "session_type": s.session_type.value,
            "session_name": s.session_name,
            "round": s.round_number,
            "half": s.half,
            "status": s.status.value,
            "results": results_list,
            "player_points": player_pts,
        })

    # Score worm data
    worm_data = _calculate_worm_data(players, sessions, calculator)

    # Draft status
    draft_mgr = _app_state.get("draft_manager")
    draft_status = draft_mgr.get_status() if draft_mgr else {"status": "not_started"}

    sync_ready = rate_limiter.can_call("sync")
    sync_wait = rate_limiter.seconds_until_ready("sync")
    force_sync_ready = rate_limiter.can_call("force_sync")
    force_sync_wait = rate_limiter.seconds_until_ready("force_sync")

    # Determine which half is currently active based on date
    from src.seed_data import CALENDAR_2026, get_halfway_round
    from datetime import date as dt_date
    today = dt_date.today()
    
    # For display: Always show original calendar (24 rounds) and Round 12 as halfway
    # Even though 2 races are cancelled, we keep the original round numbering
    total_races = 24  # Original 2026 calendar count
    halfway_round = 12  # British GP is Round 12 (halfway point)
    
    # Determine active half based on calendar
    try:
        halfway_idx = halfway_round - 1
        if halfway_idx < len(CALENDAR_2026):
            halfway_date = dt_date.fromisoformat(CALENDAR_2026[halfway_idx]["date"])
            active_half = "H2" if today > halfway_date else "H1"
        else:
            active_half = "H1"
    except (IndexError, KeyError):
        active_half = "H1"

    return {
        "leaderboard": leaderboard,
        "recent_sessions": recent_sessions,
        "worm_data": worm_data,
        "last_sync": state_mgr.last_sync if state_mgr else None,
        "total_races": total_races,
        "halfway_round": halfway_round,
        "season_year": Config.F1_SEASON_YEAR,
        "draft_status": draft_status["status"],
        "has_h2_draft": any(p.drivers_h2 for p in players),
        "active_half": active_half,
        "sync_available": sync_ready,
        "sync_wait_seconds": sync_wait,
        "force_sync_available": force_sync_ready,
        "force_sync_wait_seconds": force_sync_wait,
        "spreadsheet_url": (
            f"https://docs.google.com/spreadsheets/d/{Config.GOOGLE_SHEETS_ID}"
            if Config.GOOGLE_SHEETS_ID else None
        ),
    }


# ─── API: SYNC ───────────────────────────────────────────────────────────────

def _require_admin(token: str | None):
    """Authorize an admin-only action using the shared ADMIN_PASSWORD.

    If no ADMIN_PASSWORD is configured, the action is allowed (convenient for
    local dev); a warning is logged. When configured, a matching token must be
    supplied via the ``X-Admin-Token`` header.
    """
    expected = Config.ADMIN_PASSWORD
    if not expected:
        logger.warning(
            "Admin action allowed without a password — set ADMIN_PASSWORD to protect it."
        )
        return
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(401, "Invalid or missing admin password.")


@app.post("/api/sync")
async def trigger_sync():
    """Trigger an incremental sync - only fetches new sessions."""
    allowed, wait = rate_limiter.try_call("sync")
    if not allowed:
        raise HTTPException(429, f"Rate limited. Try again in {wait} seconds.")
    try:
        _do_sync(_app_state)
        return {"status": "ok", "message": "Sync completed"}
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        raise HTTPException(500, f"Sync failed: {str(e)}")


@app.post("/api/sync/force")
async def trigger_force_sync(x_admin_token: str | None = Header(default=None)):
    """Force a full sync - re-fetches ALL sessions from API.
    
    Use this sparingly - it will re-fetch all historical data.
    Useful for recovery or when sheets data is corrupted.

    Protected by ADMIN_PASSWORD (sent via the ``X-Admin-Token`` header).
    """
    _require_admin(x_admin_token)
    allowed, wait = rate_limiter.try_call("force_sync")
    if not allowed:
        raise HTTPException(429, f"Rate limited. Try again in {wait} seconds.")
    try:
        _do_force_sync(_app_state)
        return {"status": "ok", "message": "Force sync completed"}
    except Exception as e:
        logger.error(f"Force sync failed: {e}", exc_info=True)
        raise HTTPException(500, f"Force sync failed: {str(e)}")


# ─── API: DRIVERS ────────────────────────────────────────────────────────────

@app.get("/api/drivers")
async def get_drivers():
    """List all 20 drivers with team info."""
    players = _app_state.get("players", [])
    driver_to_player_h1: dict[str, str] = {}
    driver_to_player_h2: dict[str, str] = {}
    for p in players:
        for d in p.drivers_h1:
            driver_to_player_h1[d] = p.name
        for d in p.drivers_h2:
            driver_to_player_h2[d] = p.name

    from src.seed_data import TEAM_COLORS, COUNTRY_FLAGS
    
    return [
        {
            "number": d["number"],
            "name": d["name"],
            "team": d["team"],
            "acronym": d["acronym"],
            "country": d.get("country", ""),
            "country_flag": COUNTRY_FLAGS.get(d.get("country", ""), ""),
            "team_color": TEAM_COLORS.get(d["team"], "888888"),
            "headshot_url": d.get("headshot_url", ""),
            "owner_h1": driver_to_player_h1.get(d["name"]),
            "owner_h2": driver_to_player_h2.get(d["name"]),
        }
        for d in DRIVERS_2026
    ]


# ─── API: CHAMPIONSHIP STANDINGS ─────────────────────────────────────────────

@app.get("/api/standings")
async def get_standings():
    """Calculate F1 Driver and Constructor Championship standings from session results."""
    sessions = _app_state.get("sessions", [])
    
    # Points system for F1 (Race only)
    RACE_POINTS = {
        1: 25, 2: 18, 3: 15, 4: 12, 5: 10,
        6: 8, 7: 6, 8: 4, 9: 2, 10: 1
    }
    
    from src.seed_data import DRIVERS_2026, COUNTRY_FLAGS, TEAM_COLORS
    
    # Build driver name to team mapping (normalize names to handle case differences)
    # Session results use "Firstname LASTNAME", DRIVERS_2026 uses "Firstname Lastname"
    driver_to_team = {}
    driver_to_info = {}
    for d in DRIVERS_2026:
        # Store both formats for matching
        driver_to_team[d["name"]] = d["team"]
        driver_to_team[d["name"].upper()] = d["team"]  # FIRSTNAME LASTNAME
        driver_to_info[d["name"].upper()] = d
    
    # Track driver points
    driver_points = {}
    constructor_points = {}
    
    # Process only Race sessions (not qualifying or sprint)
    race_sessions = [s for s in sessions if s.session_type.value == "race" and s.is_finished]
    
    for session in race_sessions:
        for result in session.results:
            # Skip if DNF, DNS, or DSQ
            if result.dnf or result.dns or result.dsq:
                continue
            
            # Get points for position
            position = result.position
            if position and position in RACE_POINTS:
                points = RACE_POINTS[position]
                
                # Add to driver total (normalize name for matching)
                driver_name_raw = result.driver_name
                driver_name_normalized = driver_name_raw.upper()
                team = driver_to_team.get(driver_name_normalized, driver_to_team.get(driver_name_raw, "Unknown"))
                
                if driver_name_raw not in driver_points:
                    driver_points[driver_name_raw] = {"points": 0, "team": team}
                driver_points[driver_name_raw]["points"] += points
                
                # Add to constructor total
                if team and team != "Unknown":
                    if team not in constructor_points:
                        constructor_points[team] = 0
                    constructor_points[team] += points
    
    # Build driver standings - include ALL drivers from DRIVERS_2026
    driver_standings = []
    
    # First, create a dict with all drivers initialized to 0 points
    all_drivers = {}
    for d in DRIVERS_2026:
        all_drivers[d["name"]] = {
            "points": 0,
            "team": d["team"],
            "info": d
        }
    
    # Update with actual points from driver_points (which uses names from session results)
    for driver_name_raw, data in driver_points.items():
        driver_name_normalized = driver_name_raw.upper()
        # Find matching driver in DRIVERS_2026
        for d in DRIVERS_2026:
            if d["name"].upper() == driver_name_normalized:
                all_drivers[d["name"]]["points"] = data["points"]
                break
    
    # Sort by points (descending) and create standings
    for driver_name, data in sorted(all_drivers.items(), key=lambda x: x[1]["points"], reverse=True):
        driver_info = data["info"]
        driver_standings.append({
            "position": len(driver_standings) + 1,
            "driver": driver_name,
            "team": data["team"],
            "points": data["points"],
            "country_flag": COUNTRY_FLAGS.get(driver_info["country"], ""),
            "team_color": TEAM_COLORS.get(data["team"], "888888"),
        })
    
    # Build constructor standings - include ALL teams from DRIVERS_2026
    # Get unique teams from DRIVERS_2026
    all_teams = {}
    for d in DRIVERS_2026:
        if d["team"] not in all_teams:
            all_teams[d["team"]] = 0
    
    # Update with actual points
    for team, points in constructor_points.items():
        if team in all_teams:
            all_teams[team] = points
    
    # Sort by points (descending) and create standings
    constructor_standings = []
    for team, points in sorted(all_teams.items(), key=lambda x: x[1], reverse=True):
        constructor_standings.append({
            "position": len(constructor_standings) + 1,
            "team": team,
            "points": points,
            "team_color": TEAM_COLORS.get(team, "888888"),
        })
    
    return {
        "drivers": driver_standings,
        "constructors": constructor_standings,
        "races_counted": len(race_sessions),
    }


# ─── API: CALENDAR ───────────────────────────────────────────────────────────

@app.get("/api/calendar")
async def get_calendar():
    """Get full calendar with upcoming races including session times."""
    from src.seed_data import CALENDAR_2026, RACE_COUNTRY_FLAGS, PRESEEDED_SESSION_TIMES
    from datetime import datetime, date as dt_date, timedelta
    
    today = dt_date.today()
    api = _app_state.get("openf1_api")
    
    calendar_with_details = []
    for r in CALENDAR_2026:
        race_date = dt_date.fromisoformat(r["date"])
        is_past = race_date < today
        is_upcoming = race_date >= today
        
        # Get session details from API if available, otherwise use pre-seeded data
        sessions_info = []
        api_data_found = False
        
        if api and is_upcoming:
            try:
                # Find the meeting for this round
                meetings = api.fetch_meetings(year=2026)
                meeting = next((m for m in meetings if m.get("meeting_official_name") == r["name"]), None)
                
                if meeting:
                    raw_sessions = api.fetch_sessions(meeting.get("meeting_key"))
                    if raw_sessions:
                        api_data_found = True
                        for s in raw_sessions:
                            session_name = s.get("session_name", "")
                            date_start = s.get("date_start", "")
                            
                            # Parse datetime and convert to local time (browser will handle this)
                            session_time = ""
                            if date_start:
                                try:
                                    dt = datetime.fromisoformat(date_start.replace("Z", "+00:00"))
                                    session_time = dt.isoformat()
                                except:
                                    pass
                            
                            if session_name in ["Practice 1", "Practice 2", "Practice 3", "Qualifying", "Sprint", "Sprint Shootout", "Race"]:
                                sessions_info.append({
                                    "name": session_name,
                                    "time": session_time,
                                    "source": "api"
                                })
            except Exception as e:
                logger.debug(f"Could not fetch session details for {r['name']}: {e}")
        
        # If no API data found and race is upcoming, use pre-seeded data
        if not api_data_found and is_upcoming and r["name"] in PRESEEDED_SESSION_TIMES:
            preseeded = PRESEEDED_SESSION_TIMES[r["name"]]
            race_date_obj = dt_date.fromisoformat(preseeded["date"])
            
            for session in preseeded["sessions"]:
                # Calculate session date based on day offset from race day
                session_date = race_date_obj + timedelta(days=session["day_offset"])
                # Parse time and create datetime in PST (UTC-8)
                time_parts = session["time"].split(":")
                hour = int(time_parts[0])
                minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                
                # Create datetime in PST (UTC-8)
                session_datetime = datetime(session_date.year, session_date.month, session_date.day, hour, minute)
                # Convert PST to UTC for storage
                from datetime import timezone
                pst_offset = timedelta(hours=-8)
                session_datetime_utc = session_datetime.replace(tzinfo=timezone(pst_offset)).astimezone(timezone.utc)
                
                sessions_info.append({
                    "name": session["name"],
                    "time": session_datetime_utc.isoformat(),
                    "source": "preseeded"
                })
        
        calendar_with_details.append({
            **r,
            "half": "H1" if r["round"] <= HALFWAY_ROUND else "H2",
            "is_halfway": r["round"] == HALFWAY_ROUND,
            "is_past": is_past,
            "is_upcoming": is_upcoming,
            "country_flag": RACE_COUNTRY_FLAGS.get(r["country"], "🏁"),
            "sessions": sessions_info,
        })
    
    return calendar_with_details


# ─── API: SHARE TEXT ─────────────────────────────────────────────────────────

@app.get("/api/share-text")
async def get_share_text():
    players = _app_state.get("players", [])
    sessions = _app_state.get("sessions", [])
    calculator = _app_state.get("calculator")

    leaderboard = calculator.build_leaderboard(players, sessions)

    finished_count = sum(1 for s in sessions if s.is_finished and s.session_type.value == "race")
    rank_emojis = ["🥇", "🥈", "🥉", "4️⃣"]
    lines = [
        "🏎️🏆 *F1 2026 Fantasy Draft* 🏆🏎️",
        f"📊 Standings after {finished_count} race weekends:",
        "",
    ]
    for i, entry in enumerate(leaderboard):
        emoji = rank_emojis[i] if i < len(rank_emojis) else f"{i+1}."
        lines.append(f"{emoji} *{entry['name']}*: {entry['total']} pts (H1: {entry['h1']}, H2: {entry['h2']})")

    if len(leaderboard) >= 2:
        gap = leaderboard[0]["total"] - leaderboard[1]["total"]
        lines.append("")
        lines.append(f"📈 Gap: {leaderboard[0]['name']} leads by {gap} pts")

    if Config.DASHBOARD_URL:
        lines.append("")
        lines.append(f"🔗 _Updated live at {Config.DASHBOARD_URL}_")

    return {"text": "\n".join(lines)}


# ─── API: MID-SEASON DRAFT ──────────────────────────────────────────────────

@app.get("/api/draft/status")
async def get_draft_status():
    draft_mgr = _app_state.get("draft_manager")
    if not draft_mgr:
        raise HTTPException(500, "Draft manager not initialized")
    return draft_mgr.get_status()


@app.post("/api/draft/start")
async def start_draft(body: dict):
    """
    Start the mid-season draft.
    Body: { "randomize": true } or { "custom_order": ["Anup", "Rohit", ...] }
    """
    draft_mgr = _app_state.get("draft_manager")
    if not draft_mgr:
        raise HTTPException(500, "Draft manager not initialized")

    randomize = body.get("randomize", True)
    custom_order = body.get("custom_order")

    try:
        draft_mgr.start_draft(
            player_names=PLAYER_NAMES,
            all_drivers=get_all_driver_names(),
            randomize=randomize,
            custom_order=custom_order,
        )
        return draft_mgr.get_status()
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/draft/pick")
async def make_draft_pick(body: dict):
    """
    Make a draft pick.
    Body: { "player_name": "Abhinav", "driver_name": "Charles Leclerc" }
    """
    draft_mgr = _app_state.get("draft_manager")
    if not draft_mgr:
        raise HTTPException(500, "Draft manager not initialized")

    player = body.get("player_name")
    driver = body.get("driver_name")

    if not player or not driver:
        raise HTTPException(400, "player_name and driver_name are required")

    try:
        draft_mgr.make_pick(player, driver)
        return draft_mgr.get_status()
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/draft/undo")
async def undo_draft_pick():
    draft_mgr = _app_state.get("draft_manager")
    if not draft_mgr:
        raise HTTPException(500, "Draft manager not initialized")
    try:
        draft_mgr.undo_last_pick()
        return draft_mgr.get_status()
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/draft/reset")
async def reset_draft():
    draft_mgr = _app_state.get("draft_manager")
    if not draft_mgr:
        raise HTTPException(500, "Draft manager not initialized")
    draft_mgr.reset_draft()
    return draft_mgr.get_status()


@app.post("/api/draft/finalize")
async def finalize_draft():
    """Finalize the H2 draft: save picks to Google Sheets."""
    draft_mgr = _app_state.get("draft_manager")
    sheets_client = _app_state.get("sheets_client")

    if not draft_mgr:
        raise HTTPException(500, "Draft manager not initialized")

    if not draft_mgr.state.is_complete:
        raise HTTPException(400, "Draft is not yet complete")

    # Update players with H2 picks
    picks_by_player = draft_mgr.state.picks_by_player
    players = _app_state.get("players", [])

    for player in players:
        if player.name in picks_by_player:
            player.drivers_h2 = picks_by_player[player.name]

    # Save to Google Sheets
    if sheets_client:
        from src.sheets.players import write_draft_picks_h2
        try:
            write_draft_picks_h2(sheets_client, players)
            logger.info("H2 draft picks saved to Google Sheets")
        except Exception as e:
            logger.error(f"Failed to save H2 picks to sheets: {e}")
            raise HTTPException(500, f"Failed to save to sheets: {str(e)}")
    else:
        logger.warning("No sheets client — H2 picks saved in memory only")

    return {
        "status": "finalized",
        "picks_by_player": picks_by_player,
        "message": "H2 draft picks saved successfully!",
    }


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _calculate_worm_data(
    players: list[DraftPlayer],
    sessions: list[Session],
    calculator: ScoringCalculator,
) -> dict:
    """Calculate cumulative points by date for the score worm chart."""
    finished = [s for s in sessions if s.is_finished or s.is_live]
    if not finished:
        return {"dates": [], "labels": [], "players": {p.name: [] for p in players}}

    finished.sort(key=lambda s: s.session_date)

    all_dates = sorted(set(s.session_date for s in finished))
    if all_dates:
        start_date = all_dates[0] - timedelta(days=1)
        all_dates = [start_date] + all_dates

    # Build date labels with race names
    date_labels = []
    for d in all_dates:
        day_sessions = [s for s in finished if s.session_date == d]
        if day_sessions:
            # Get the GP name (use short form)
            gp_name = day_sessions[0].grand_prix.replace(" Grand Prix", "")
            # Get session type abbreviation
            session_types = set(s.session_type.value[0].upper() for s in day_sessions)
            session_abbr = "/".join(sorted(session_types))
            label = f"{gp_name} ({session_abbr})"
        else:
            label = d.strftime("%b %d")
        date_labels.append(label)

    player_cumulative: dict[str, list[float]] = {p.name: [] for p in players}
    running: dict[str, float] = {p.name: 0.0 for p in players}

    for d in all_dates:
        day_sessions = [s for s in finished if s.session_date == d]
        for session in day_sessions:
            for player in players:
                running[player.name] += calculator.calculate_player_session_points(
                    player, session
                )
        for player in players:
            player_cumulative[player.name].append(round(running[player.name], 2))

    # Find halfway boundary
    halfway_index = None
    for i, d in enumerate(all_dates):
        day_sessions = [s for s in finished if s.session_date == d and s.round_number > HALFWAY_ROUND]
        if day_sessions and halfway_index is None:
            halfway_index = i
            break

    return {
        "dates": [d.isoformat() for d in all_dates],
        "labels": date_labels,
        "players": player_cumulative,
        "halfway_index": halfway_index,
    }


def _do_sync(state: dict):
    """Execute a sync cycle - only fetch NEW sessions from API.
    
    Design:
    - Google Sheets is the source of truth for historical data
    - On startup, sessions are loaded from sheets
    - During sync, we only fetch sessions not already in sheets
    - New results are written to sheets immediately
    """
    from src.sheets.results import write_results, read_results
    from src.sheets.scores import write_leaderboard

    openf1 = state.get("openf1_api")
    sheets_client = state.get("sheets_client")
    state_mgr = state.get("state_manager")
    players = state.get("players", [])
    calculator = state.get("calculator")

    if not openf1:
        logger.warning("No OpenF1 API client — skipping sync")
        return

    # Get existing sessions (from sheets, loaded on startup)
    existing_sessions = state.get("sessions", [])
    
    # IMPORTANT: Sessions loaded from sheets have SYNTHETIC session_keys (round*100+type)
    # but the OpenF1 API uses REAL session_keys (like 9876, 9877...).
    # We must track which (round_number, session_type) combos we already have,
    # and also pass real API keys to exclude_keys for sessions we got from the API previously.
    existing_identities = {(s.round_number, s.session_type.value) for s in existing_sessions}
    
    # Collect real API session keys (non-synthetic ones, i.e. not round*100+offset)
    # Synthetic keys are always < 3000 (max round 24 * 100 + 3 = 2403)
    real_api_keys = {s.session_key for s in existing_sessions if s.session_key > 3000}
    
    # Get list of session keys we've already scored (from state manager)
    scored_keys = set()
    if state_mgr:
        scored_keys = set(state_mgr.state.get("scored_session_keys", []))
    
    # Combine real API keys + scored keys for the API filter
    known_keys = real_api_keys | scored_keys
    
    logger.info(f"Sync: {len(existing_sessions)} sessions loaded, "
                f"{len(existing_identities)} unique (round,type) combos, "
                f"{len(real_api_keys)} real API keys, {len(scored_keys)} scored")

    try:
        # Fetch only NEW sessions from API
        # Pass both real API keys AND (round, type) identities to skip
        # This prevents expensive API calls for sessions we already have from sheets
        new_sessions = openf1.fetch_new_sessions(
            exclude_keys=known_keys,
            exclude_identities=existing_identities,
        )
        
        # Double-check: filter out any that slipped through
        truly_new = [
            s for s in new_sessions 
            if (s.round_number, s.session_type.value) not in existing_identities
        ]
        
        if len(truly_new) < len(new_sessions):
            logger.info(f"Filtered {len(new_sessions) - len(truly_new)} sessions already in sheets "
                       f"(key mismatch but same round+type)")
        new_sessions = truly_new
        
        logger.info(f"API returned {len(new_sessions)} genuinely new sessions to process")
    except Exception as e:
        logger.error(f"OpenF1 API fetch failed: {e}")
        if state_mgr:
            state_mgr.record_error(str(e))
        return

    if not new_sessions:
        logger.info("No new sessions to sync")
        # Still update the leaderboard in case players changed
        if sheets_client and existing_sessions:
            try:
                write_leaderboard(sheets_client, players, existing_sessions, calculator)
            except Exception as e:
                logger.warning(f"Failed to update leaderboard: {e}")
        return

    # Merge new sessions with existing, deduplicating by (round_number, session_type)
    # This is the reliable identity since session_key may differ between sheets and API
    # New sessions take precedence over existing ones (fresher data from API)
    session_map = {}
    for s in existing_sessions:
        key = (s.round_number, s.session_type.value)
        session_map[key] = s
    for s in new_sessions:
        key = (s.round_number, s.session_type.value)
        session_map[key] = s  # Overwrite with fresher API data
    
    all_sessions = sorted(session_map.values(), key=lambda s: (s.session_date, s.session_type.value))
    state["sessions"] = all_sessions

    # Write ALL results to sheets (this overwrites, ensuring consistency)
    if sheets_client:
        try:
            write_results(sheets_client, all_sessions, calculator)
            write_leaderboard(sheets_client, players, all_sessions, calculator)
            logger.info(f"Wrote {len(all_sessions)} sessions to sheets")
        except Exception as e:
            logger.error(f"Failed to write to sheets: {e}")

    # Mark new sessions as scored
    if state_mgr:
        for s in new_sessions:
            if s.is_finished and s.results:
                state_mgr.mark_session_scored(s.session_key)
        state_mgr.mark_synced()

    logger.info(f"Sync completed: {len(new_sessions)} new sessions, "
                f"{len(all_sessions)} total tracked")


def _do_force_sync(state: dict):
    """Execute a FULL sync - re-fetch all sessions from API.
    
    Use this for recovery when sheets data is corrupted or missing.
    This will make many API calls and may hit rate limits.
    """
    from src.sheets.results import write_results
    from src.sheets.scores import write_leaderboard

    openf1 = state.get("openf1_api")
    sheets_client = state.get("sheets_client")
    state_mgr = state.get("state_manager")
    players = state.get("players", [])
    calculator = state.get("calculator")

    if not openf1:
        logger.warning("No OpenF1 API client — skipping force sync")
        return

    logger.info("Force sync: Re-fetching ALL sessions from API...")

    try:
        # Fetch ALL sessions (no exclusions)
        all_sessions = openf1.fetch_all_scored_sessions()
        logger.info(f"Force sync: API returned {len(all_sessions)} sessions")
    except Exception as e:
        logger.error(f"Force sync: OpenF1 API fetch failed: {e}")
        if state_mgr:
            state_mgr.record_error(str(e))
        return

    # Update in-memory state
    state["sessions"] = all_sessions

    # Write ALL results to sheets
    if sheets_client:
        try:
            write_results(sheets_client, all_sessions, calculator)
            write_leaderboard(sheets_client, players, all_sessions, calculator)
            logger.info(f"Force sync: Wrote {len(all_sessions)} sessions to sheets")
        except Exception as e:
            logger.error(f"Force sync: Failed to write to sheets: {e}")

    # Mark all sessions as scored
    if state_mgr:
        # Clear old scored keys and re-add
        state_mgr.state["scored_session_keys"] = []
        for s in all_sessions:
            if s.is_finished and s.results:
                state_mgr.mark_session_scored(s.session_key)
        state_mgr.mark_synced()
        state_mgr.save()

    logger.info(f"Force sync completed: {len(all_sessions)} sessions tracked")


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

def start():
    """Entry point for starting the web server."""
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="F1 2026 Fantasy Draft Server")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    port = args.port or int(os.environ.get("PORT", "8000"))
    uvicorn.run("src.server:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    start()
