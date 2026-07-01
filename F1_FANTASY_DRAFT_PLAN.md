# F1 Fantasy Draft — Project Plan

> A Formula 1 fantasy draft app, modelled on the FIFA 2026 Fantasy Draft architecture.
> Players pick 5 of the 20 F1 drivers and earn points based on Qualifying, Feature Race, and Sprint Race finishing positions throughout the season.

---

## 1. Concept Mapping: FIFA → F1

| FIFA Project | F1 Project | Notes |
|---|---|---|
| National Team (48) | F1 Driver (20) | Each player drafts **5 drivers** (instead of 10 teams) |
| Match | Session (Qualifying / Sprint / Race) | Points come from session finishing positions |
| Match Stage (Group, R16, QF…) | Session Type (Qualifying, Sprint, Race) | Different point tables per type |
| Match Score (goals, win/draw) | Finishing Position (P1–P15/P10) | Position → points lookup |
| Tournament (one-off) | Season (24 race weekends) | Runs March–December |
| football-data.org API | **openf1.org** API | Free, no API key for historical data |

---

## 2. Points Scoring System

### 2a. Qualifying (Top 10 score)

| Position | Points |
|----------|--------|
| P1 | 10 |
| P2 | 9 |
| P3 | 8 |
| P4 | 7 |
| P5 | 6 |
| P6 | 5 |
| P7 | 4 |
| P8 | 3 |
| P9 | 2 |
| P10 | 1 |
| P11+ | 0 |

### 2b. Feature Race (Top 15 score)

| Position | Points |
|----------|--------|
| P1 | 50 |
| P2 | 40 |
| P3 | 35 |
| P4 | 30 |
| P5 | 25 |
| P6 | 20 |
| P7 | 18 |
| P8 | 16 |
| P9 | 14 |
| P10 | 12 |
| P11 | 10 |
| P12 | 9 |
| P13 | 8 |
| P14 | 7 |
| P15 | 5 |
| P16+ / DNF / DNS | 0 |

### 2c. Sprint Race (Top 10 score, not every GP)

| Position | Points |
|----------|--------|
| P1 | 10 |
| P2 | 9 |
| P3 | 8 |
| P4 | 7 |
| P5 | 6 |
| P6 | 5 |
| P7 | 4 |
| P8 | 3 |
| P9 | 2 |
| P10 | 1 |
| P11+ / DNF / DNS | 0 |

---

## 3. OpenF1 API — Key Endpoints

All endpoints are at `https://api.openf1.org/v1/`. Free tier: 3 req/s, 30 req/min. No authentication needed for historical data.

| Endpoint | Purpose | Example |
|---|---|---|
| `GET /meetings?year=2025` | List all Grand Prix weekends in a season | Returns `meeting_key`, dates, circuit, country |
| `GET /sessions?meeting_key=X` | List sessions (Practice, Qualifying, Sprint, Race) for a GP | Returns `session_key`, `session_name`, `session_type`, dates |
| `GET /session_result?session_key=X` | **Final finishing positions** — the core data for scoring | Returns `driver_number`, `position`, `dnf`, `dns`, `dsq` |
| `GET /drivers?session_key=X` | Driver info (name, team, number, headshot) | Returns `full_name`, `driver_number`, `team_name`, `name_acronym` |
| `GET /position?session_key=X` | Real-time position changes during a live session | For live dashboard updates |

### API Data Flow
```
1. Fetch meetings for the season     → list of GP weekends
2. For each meeting, fetch sessions  → find Qualifying / Sprint / Race session_keys
3. For each session, fetch results   → get final positions per driver
4. Map driver_number → driver name   → look up from /drivers endpoint
5. Apply points table                → Qualifying / Sprint / Race rules
6. Aggregate per drafted driver      → sum points across all sessions
```

### Session Name Mapping

The OpenF1 `session_name` values we care about:

| `session_name` | Maps To | Points Table |
|---|---|---|
| `"Qualifying"` | Qualifying | Top-10 table |
| `"Sprint"` | Sprint Race | Top-10 table |
| `"Race"` | Feature Race | Top-15 table |
| `"Sprint Qualifying"` | *(ignored — no points)* | — |
| `"Practice 1/2/3"` | *(ignored — no points)* | — |

---

## 4. Directory Structure

Mirror the FIFA project structure, adapted for F1:

```
f1-fantasy-draft/
├── credentials.json              # Google Sheets service account (local dev)
├── credentials.json.example
├── .env.example
├── pyproject.toml
├── requirements.txt
├── Procfile                      # For Render deployment
├── LICENSE
├── README.md
│
├── src/
│   ├── config.py                 # Env-based config (sheets, API, sync, etc.)
│   ├── main.py                   # CLI entry point / app orchestrator
│   ├── server.py                 # FastAPI dashboard + API endpoints
│   ├── demo.py                   # Demo mode with pre-seeded data
│   ├── seed_data.py              # 2025 F1 season drivers & calendar
│   ├── validation.py             # Data integrity & factual checks
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── driver.py             # Was: team.py — F1 driver model
│   │   ├── session.py            # Was: match.py — Quali/Sprint/Race session
│   │   ├── draft_pick.py         # Player → driver mapping
│   │   └── player.py             # Fantasy player (person drafting)
│   │
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── rules.py              # Points tables for Q/Sprint/Race
│   │   └── calculator.py         # Position → points logic
│   │
│   ├── data_sources/
│   │   ├── __init__.py
│   │   ├── openf1_api.py         # Was: football_api.py — OpenF1 client
│   │   ├── openf1_api_stub.py    # Was: football_api_stub.py — for demo/tests
│   │   └── llm_fallback.py       # Optional ChatGPT validation
│   │
│   ├── sheets/
│   │   ├── __init__.py
│   │   ├── client.py             # Google Sheets auth wrapper (REUSE AS-IS)
│   │   ├── players.py            # Draft Picks tab read/write
│   │   ├── schedule.py           # Race Calendar tab read/write
│   │   ├── results.py            # NEW: Session Results tab read/write
│   │   ├── scores.py             # Leaderboard tab
│   │   ├── scoring_rules.py      # Scoring Rules reference tab
│   │   └── formatting.py         # Conditional formatting
│   │
│   ├── sync/
│   │   ├── __init__.py
│   │   ├── scheduler.py          # APScheduler for auto-sync (REUSE AS-IS)
│   │   ├── state_manager.py      # Crash recovery state (REUSE AS-IS)
│   │   └── recovery.py           # Reconciliation logic
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py             # Logging setup (REUSE AS-IS)
│       ├── rate_limiter.py       # API rate limiting (REUSE AS-IS)
│       └── retry.py              # Retry decorator (REUSE AS-IS)
│
├── state/
│   └── last_sync.json
│
├── static/
│   └── index.html                # Dashboard UI
│
├── templates/
│   ├── scoring_rules.json
│   └── sheet_schema.json
│
├── tests/
│   ├── __init__.py
│   ├── test_openf1_api.py
│   ├── test_scoring.py
│   ├── test_sheets_client.py
│   ├── test_sync.py
│   ├── test_recovery.py
│   └── test_validation.py
│
└── docs/
    ├── SETUP_OPENF1.md
    ├── SETUP_GOOGLE_SHEETS.md
    ├── DEMO_MODE.md
    ├── SYNC_CONFIGURATION.md
    └── TESTING_GUIDE.md
```

---

## 5. Module-by-Module Design

### 5a. `src/models/driver.py` (replaces `team.py`)

```python
class Driver(BaseModel):
    """An F1 driver in the 2025 season."""
    driver_number: int              # e.g. 1, 44, 63
    full_name: str                  # e.g. "Max Verstappen"
    name_acronym: str               # e.g. "VER"
    team_name: str                  # e.g. "Red Bull Racing"
    headshot_url: Optional[str]     # Photo URL from OpenF1
```

### 5b. `src/models/session.py` (replaces `match.py`)

```python
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
    position: Optional[int]         # Final position (None if DNF/DNS)
    dnf: bool = False
    dns: bool = False
    dsq: bool = False
    points_earned: float = 0.0      # Calculated fantasy points

class Session(BaseModel):
    """A single scored session (Qualifying, Sprint, or Race)."""
    session_key: int                # OpenF1 unique ID
    meeting_key: int                # Parent GP weekend
    session_type: SessionType
    session_name: str               # e.g. "Race", "Qualifying"
    grand_prix: str                 # e.g. "British Grand Prix"
    circuit: str                    # e.g. "Silverstone"
    country: str
    date: date
    status: SessionStatus
    results: list[SessionResult] = []
```

### 5c. `src/models/player.py` (adapted)

```python
class DraftPlayer(BaseModel):
    """A person participating in the fantasy draft."""
    name: str                       # e.g. "Abhinav"
    drivers: list[int] = []         # List of driver_numbers picked (5 drivers)
    total_points: float = 0.0

    @property
    def driver_count(self) -> int:
        return len(self.drivers)
```

### 5d. `src/models/draft_pick.py` (adapted)

```python
class DraftPick(BaseModel):
    """Maps a fantasy player to a drafted F1 driver."""
    player_name: str
    driver_number: int
    driver_name: str                # Denormalized for display
    pick_order: int = 0
```

### 5e. `src/scoring/rules.py`

```python
@dataclass(frozen=True)
class ScoringRules:
    """Points tables for each session type."""

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
        table = {
            SessionType.QUALIFYING: self.qualifying_points,
            SessionType.RACE: self.race_points,
            SessionType.SPRINT: self.sprint_points,
        }[session_type]
        return table.get(position, 0)
```

### 5f. `src/scoring/calculator.py`

```python
class ScoringCalculator:
    """Calculates fantasy points from session results."""

    def calculate_session_points(self, session: Session) -> dict[int, float]:
        """
        Returns {driver_number: points} for all drivers in a session.
        DNF/DNS/DSQ drivers get 0 points.
        """
        points_map = {}
        for result in session.results:
            if result.dnf or result.dns or result.dsq or result.position is None:
                points_map[result.driver_number] = 0.0
            else:
                points_map[result.driver_number] = self.rules.get_points(
                    session.session_type, result.position
                )
        return points_map

    def calculate_player_total(
        self, player_drivers: list[int], sessions: list[Session]
    ) -> float:
        """Total points for a fantasy player across all scored sessions."""
        total = 0.0
        for session in sessions:
            pts = self.calculate_session_points(session)
            for driver_num in player_drivers:
                total += pts.get(driver_num, 0.0)
        return total
```

### 5g. `src/data_sources/openf1_api.py` (replaces `football_api.py`)

```python
class OpenF1API:
    """Client for the OpenF1 REST API (https://api.openf1.org/v1/)."""

    BASE_URL = "https://api.openf1.org/v1"

    # Session types we care about for scoring
    SCORED_SESSION_TYPES = {"Qualifying", "Sprint", "Race"}

    def fetch_season_meetings(self, year: int) -> list[dict]:
        """GET /meetings?year=YYYY → all GP weekends."""

    def fetch_sessions(self, meeting_key: int) -> list[dict]:
        """GET /sessions?meeting_key=X → all sessions for a GP."""

    def fetch_session_results(self, session_key: int) -> list[dict]:
        """GET /session_result?session_key=X → final positions."""

    def fetch_drivers(self, session_key: int) -> list[dict]:
        """GET /drivers?session_key=X → driver info for a session."""

    def fetch_all_scored_sessions(self, year: int) -> list[Session]:
        """
        High-level: fetch all meetings → sessions → results for the season.
        Filters to only Qualifying, Sprint, and Race sessions.
        Returns fully populated Session objects with results.
        """

    def fetch_live_positions(self, session_key: int) -> list[dict]:
        """GET /position?session_key=X → real-time positions (for live mode)."""
```

**Key implementation detail:** The OpenF1 `session_result` endpoint returns `driver_number` and `position`. We need a driver cache (number → name/team) built from the `/drivers` endpoint so we can display names in the sheet.

### 5h. `src/sheets/` modules

**Reuse as-is:**
- `client.py` — Google Sheets auth (identical)
- `formatting.py` — Conditional formatting

**Adapt:**

| Tab | Sheet Module | Columns |
|---|---|---|
| **Draft Picks** | `players.py` | `Player`, `Driver 1`, `Driver 2`, `Driver 3`, `Driver 4`, `Driver 5` |
| **Race Calendar** | `schedule.py` | `Date`, `Grand Prix`, `Circuit`, `Country`, `Has Sprint`, `Status` |
| **Session Results** | `results.py` *(new)* | `Date`, `Grand Prix`, `Session Type`, `Driver`, `Position`, `DNF`, `Points`, `Status` |
| **Leaderboard** | `scores.py` | `Rank`, `Player`, `Total Points`, `Driver 1 (pts)`, `Driver 2 (pts)`, … |
| **Scoring Rules** | `scoring_rules.py` | Reference tab with the three points tables |

### 5i. `src/sync/` — Mostly reuse

- `scheduler.py` — **Reuse as-is.** Same interval-based + live-mode adaptive scheduling.
- `state_manager.py` — **Reuse as-is.** Tracks `scored_session_keys` instead of `scored_match_ids`.
- `recovery.py` — **Adapt.** Compare sessions in sheet vs API to find unscored ones.

### 5j. `src/config.py`

```python
class Config:
    # --- Google Sheets --- (same as FIFA project)
    GOOGLE_SHEETS_CREDENTIALS_JSON: str
    GOOGLE_SHEETS_CREDENTIALS_FILE: str
    GOOGLE_SHEETS_ID: str

    # --- OpenF1 API ---
    OPENF1_BASE_URL: str = "https://api.openf1.org/v1"
    F1_SEASON_YEAR: int = 2025              # Which season to track

    # --- OpenAI (optional validation) ---
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"

    # --- Sync ---
    SYNC_INTERVAL_MINUTES: int = 60
    SYNC_LIVE_INTERVAL_SECONDS: int = 120
    SYNC_TIMEZONE: str = "Asia/Kolkata"

    # --- State ---
    STATE_FILE: str

    # --- Server ---
    PORT: int = 8000
```

**Note:** No `OPENF1_API_KEY` needed — the free tier has no auth for historical data.

---

## 6. Google Sheet Layout

### Tab 1: "Draft Picks"
```
| Player    | Driver 1       | Driver 2        | Driver 3        | Driver 4     | Driver 5      |
|-----------|----------------|-----------------|-----------------|--------------|---------------|
| Abhinav   | Max Verstappen | Lando Norris    | Charles Leclerc | Lewis Hamilton | Oscar Piastri |
| Friend1   | Carlos Sainz   | George Russell  | Fernando Alonso | Pierre Gasly  | Yuki Tsunoda  |
| Friend2   | ...            | ...             | ...             | ...          | ...           |
| Friend3   | ...            | ...             | ...             | ...          | ...           |
```

### Tab 2: "Race Calendar"
```
| Date       | Grand Prix         | Circuit          | Country    | Has Sprint | Status    |
|------------|--------------------|------------------|------------|------------|-----------|
| 2025-03-16 | Australian GP      | Albert Park      | Australia  | No         | finished  |
| 2025-03-23 | Chinese GP         | Shanghai         | China      | Yes        | finished  |
| ...        | ...                | ...              | ...        | ...        | ...       |
```

### Tab 3: "Session Results"
```
| Date       | Grand Prix    | Session    | Driver          | #  | Position | DNF | Points |
|------------|---------------|------------|-----------------|-----|----------|-----|--------|
| 2025-03-15 | Australian GP | Qualifying | Max Verstappen  | 1   | 1        | No  | 10     |
| 2025-03-15 | Australian GP | Qualifying | Lando Norris    | 4   | 2        | No  | 9      |
| ...        | ...           | ...        | ...             | ... | ...      | ... | ...    |
| 2025-03-16 | Australian GP | Race       | Max Verstappen  | 1   | 1        | No  | 50     |
| 2025-03-16 | Australian GP | Race       | Lando Norris    | 4   | 3        | No  | 35     |
```

### Tab 4: "Leaderboard"
```
| Rank | Player  | Total Pts | Verstappen (pts) | Norris (pts) | Leclerc (pts) | Hamilton (pts) | Piastri (pts) |
|------|---------|-----------|------------------|--------------|---------------|----------------|---------------|
| 1    | Abhinav | 342       | 120              | 95           | 72            | 30             | 25            |
| 2    | Friend1 | 298       | ...              | ...          | ...           | ...            | ...           |
```

### Tab 5: "Scoring Rules"
```
| Session Type | Position | Points |
|--------------|----------|--------|
| Qualifying   | P1       | 10     |
| Qualifying   | P2       | 9      |
| ...          | ...      | ...    |
| Race         | P1       | 50     |
| Race         | P2       | 40     |
| ...          | ...      | ...    |
| Sprint       | P1       | 10     |
| ...          | ...      | ...    |
```

---

## 7. Sync Flow (adapted from FIFA project)

```
┌─────────────────────────────────┐
│  Scheduler triggers sync        │
│  (every 60 min / 2 min live)    │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  1. Load state from disk        │
│     (scored_session_keys)       │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  2. OpenF1API.fetch_meetings()  │
│     → list of GP weekends       │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  3. For each meeting:           │
│     fetch_sessions()            │
│     → filter to Q/Sprint/Race   │
│     → skip already-scored keys  │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  4. For new finished sessions:  │
│     fetch_session_results()     │
│     → get final positions       │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  5. ScoringCalculator           │
│     position → fantasy points   │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  6. Update Google Sheets        │
│     - Session Results tab       │
│     - Leaderboard tab           │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  7. Save state to disk          │
│     (mark sessions as scored)   │
└─────────────────────────────────┘
```

---

## 8. FastAPI Endpoints (same pattern as FIFA project)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Dashboard HTML (static page) |
| `GET` | `/api/status` | Leaderboard, last sync, upcoming GP |
| `POST` | `/api/sync` | Trigger score sync (rate limited) |
| `POST` | `/api/validate` | Trigger data validation |
| `GET` | `/api/share-text` | Formatted standings for WhatsApp |
| `GET` | `/api/drivers` | List all 20 drivers with teams |
| `GET` | `/api/calendar` | Race calendar with status |
| `GET` | `/api/results/{meeting_key}` | Results for a specific GP |

---

## 9. Seed Data (`src/seed_data.py`)

Hardcode the 2025 F1 grid (20 drivers) and calendar (~24 GPs). This is used to:
1. Initialize the Google Sheet on first run
2. Provide fallback if the API is unreachable
3. Power demo mode

```python
DRIVERS_2025 = [
    {"number": 1,  "name": "Max Verstappen",    "team": "Red Bull Racing",   "acronym": "VER"},
    {"number": 4,  "name": "Lando Norris",       "team": "McLaren",           "acronym": "NOR"},
    {"number": 81, "name": "Oscar Piastri",      "team": "McLaren",           "acronym": "PIA"},
    {"number": 16, "name": "Charles Leclerc",    "team": "Ferrari",           "acronym": "LEC"},
    {"number": 44, "name": "Lewis Hamilton",     "team": "Ferrari",           "acronym": "HAM"},
    {"number": 63, "name": "George Russell",     "team": "Mercedes",          "acronym": "RUS"},
    {"number": 12, "name": "Andrea Kimi Antonelli", "team": "Mercedes",      "acronym": "ANT"},
    {"number": 14, "name": "Fernando Alonso",    "team": "Aston Martin",      "acronym": "ALO"},
    {"number": 18, "name": "Lance Stroll",       "team": "Aston Martin",      "acronym": "STR"},
    {"number": 10, "name": "Pierre Gasly",       "team": "Alpine",            "acronym": "GAS"},
    {"number": 5,  "name": "Jack Doohan",        "team": "Alpine",            "acronym": "DOO"},
    {"number": 22, "name": "Yuki Tsunoda",       "team": "RB",               "acronym": "TSU"},
    {"number": 30, "name": "Liam Lawson",        "team": "Red Bull Racing",   "acronym": "LAW"},
    {"number": 27, "name": "Nico Hulkenberg",    "team": "Sauber",            "acronym": "HUL"},
    {"number": 87, "name": "Gabriel Bortoleto",  "team": "Sauber",            "acronym": "BOR"},
    {"number": 23, "name": "Alexander Albon",    "team": "Williams",          "acronym": "ALB"},
    {"number": 55, "name": "Carlos Sainz",       "team": "Williams",          "acronym": "SAI"},
    {"number": 31, "name": "Esteban Ocon",       "team": "Haas",              "acronym": "OCO"},
    {"number": 87, "name": "Oliver Bearman",     "team": "Haas",              "acronym": "BEA"},
    {"number": 6,  "name": "Isack Hadjar",       "team": "RB",               "acronym": "HAD"},
]

CALENDAR_2025 = [
    {"round": 1,  "name": "Australian GP",      "circuit": "Albert Park",     "country": "Australia",  "date": "2025-03-16", "sprint": False},
    {"round": 2,  "name": "Chinese GP",         "circuit": "Shanghai",        "country": "China",      "date": "2025-03-23", "sprint": True},
    # ... all 24 rounds
]
```

---

## 10. What to Reuse vs Rewrite

### ✅ Reuse As-Is (copy directly)
- `src/sheets/client.py` — Google Sheets auth (identical)
- `src/utils/logger.py` — Logging setup
- `src/utils/rate_limiter.py` — API rate limiting
- `src/utils/retry.py` — Retry decorator
- `src/sync/scheduler.py` — APScheduler wrapper
- `src/sync/state_manager.py` — State persistence (rename `scored_match_ids` → `scored_session_keys`)
- `src/config.py` — Structure (swap football config for OpenF1 config)
- `credentials.json.example`, `Procfile`, `pyproject.toml` structure

### 🔄 Adapt (same pattern, different data)
- `src/models/` — New models for Driver, Session, SessionResult (replaces Team, Match)
- `src/scoring/rules.py` — Position-based lookup tables (replaces win/draw/goal rules)
- `src/scoring/calculator.py` — Position → points (replaces goals/result → points)
- `src/sheets/players.py` — "Draft Picks" tab (5 drivers instead of 10 teams)
- `src/sheets/schedule.py` → `src/sheets/calendar.py` — Race calendar tab
- `src/sheets/scores.py` — Leaderboard (drivers instead of teams)
- `src/server.py` — Same FastAPI structure, different data models
- `src/main.py` — Same orchestrator pattern, uses OpenF1API
- `src/demo.py` — Generate fake F1 results instead of fake football matches
- `src/validation.py` — Validate session results instead of match scores
- `src/sync/recovery.py` — Compare session_keys instead of match_ids
- `static/index.html` — F1-themed dashboard
- All test files — Test F1 models and scoring

### 🆕 New Files
- `src/sheets/results.py` — Session Results tab (new granularity: per-driver-per-session)
- `src/data_sources/openf1_api.py` — OpenF1 client (replaces football-data.org client)
- `src/data_sources/openf1_api_stub.py` — Stub for demo/testing
- `src/seed_data.py` — 2025 F1 driver grid + calendar

---

## 11. `requirements.txt`

```
# Google Sheets
gspread>=6.1.0
google-auth>=2.29.0

# HTTP / API
requests>=2.31.0
httpx>=0.27.0

# OpenAI (optional ChatGPT validation)
openai>=1.35.0

# Web server
fastapi>=0.111.0
uvicorn[standard]>=0.30.0

# Scheduling
apscheduler>=3.10.4

# Environment
python-dotenv>=1.0.1

# Data models
pydantic>=2.7.0

# Testing
pytest>=8.2.0
pytest-asyncio>=0.23.0

# Utilities
tenacity>=8.3.0
```

*(Same as FIFA project — no extra dependencies needed since OpenF1 is a simple REST API.)*

---

## 12. Implementation Order

Build in this order, testing as you go:

| Phase | Files | What to Test |
|-------|-------|-------------|
| **1. Models** | `models/driver.py`, `models/session.py`, `models/player.py`, `models/draft_pick.py` | Unit tests for model creation, enums |
| **2. Scoring** | `scoring/rules.py`, `scoring/calculator.py` | All points tables, edge cases (DNF/DNS/DSQ, P16+) |
| **3. OpenF1 Client** | `data_sources/openf1_api.py`, `data_sources/openf1_api_stub.py` | API parsing, session filtering, driver cache |
| **4. Seed Data** | `seed_data.py` | 20 drivers, 24 GPs, sprint weekends |
| **5. Sheets** | `sheets/client.py` (copy), `sheets/players.py`, `sheets/calendar.py`, `sheets/results.py`, `sheets/scores.py`, `sheets/scoring_rules.py` | Read/write roundtrip |
| **6. Sync** | `sync/state_manager.py` (copy), `sync/scheduler.py` (copy), `sync/recovery.py` | State persistence, session reconciliation |
| **7. Config** | `config.py` | Env var loading, validation |
| **8. Server** | `server.py`, `static/index.html` | Dashboard rendering, API endpoints |
| **9. Demo** | `demo.py` | Pre-seeded data, progressive reveal |
| **10. Main** | `main.py` | Full app lifecycle |
| **11. Validation** | `validation.py` | Points recalculation, data integrity |

---

## 13. Key Differences to Watch Out For

| Concern | FIFA Project | F1 Project |
|---------|-------------|------------|
| **Scoring granularity** | Per-match (2 teams score per match) | Per-session per-driver (20 drivers per session) |
| **Session types** | One type (match) with stage multipliers | Three types (Q/Sprint/Race) with different tables |
| **Season duration** | 1 month tournament | 9-month season (March–December) |
| **Draft size** | 10 teams per player | 5 drivers per player |
| **Total entities** | 48 teams | 20 drivers |
| **Data volume** | ~104 matches | ~24 GPs × 2–3 scored sessions = ~60–72 sessions |
| **API auth** | API key required | No auth needed (free tier) |
| **Sprint weekends** | N/A | Only ~6 of 24 GPs have sprints |
| **DNF/DNS handling** | N/A (teams always finish) | Drivers can DNF/DNS/DSQ → 0 points |
| **Live detection** | Match `status: IN_PLAY` | Session `date_start`/`date_end` window |

---

## 14. Environment Variables (`.env`)

```bash
# Google Sheets (same as FIFA project)
GOOGLE_SHEETS_ID=your-spreadsheet-id
GOOGLE_SHEETS_CREDENTIALS_JSON=  # For hosted (Render)
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json  # For local dev

# OpenF1 (no API key needed!)
F1_SEASON_YEAR=2025

# OpenAI (optional, for validation)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Sync schedule
SYNC_INTERVAL_MINUTES=60
SYNC_LIVE_INTERVAL_SECONDS=120
SYNC_TIMEZONE=Asia/Kolkata

# Server
PORT=8000
LOG_LEVEL=INFO

# Demo mode
DEMO_GOOGLE_SHEETS_ID=  # Optional separate sheet for demo
```

---

## 15. Dashboard UI Sections

The `static/index.html` dashboard should show:

1. **Leaderboard** — Ranked fantasy players with total points and per-driver breakdown
2. **Next GP** — Upcoming Grand Prix with countdown, session times
3. **Recent Results** — Last completed session results with points earned
4. **Season Calendar** — All GPs with completion status
5. **Driver Grid** — All 20 drivers with teams, who drafted whom, season points
6. **Sync Status** — Last sync time, next auto-sync, manual sync button

---

*This plan follows the FIFA Fantasy Draft architecture pattern: Google Sheets as the persistent store and source of truth, a REST API for live data, FastAPI for the dashboard, APScheduler for automatic syncing, and state persistence for crash recovery.*
