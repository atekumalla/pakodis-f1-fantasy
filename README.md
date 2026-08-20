# F1 2026 Fantasy Draft 🏎️

A Formula 1 fantasy draft app for the 2026 season. Four players each draft 5 F1 drivers and earn points based on Qualifying, Race, and Sprint results throughout the season.

## 🎯 Features

### Core Functionality
- **Live Scoring** — Real-time data from the OpenF1 API (free, no API key required)
- **Google Sheets Backend** — Spreadsheet acts as the single source of truth for all historical data
- **Intelligent Sync System** — Adaptive scheduling with rate limiting and error recovery
  - Hourly sync during regular periods (60 minutes)
  - Live session mode (2-minute intervals) when races are in progress
  - Incremental updates (only fetch new sessions)
  - Force sync option to re-fetch all data from API
- **Mid-Season Redraft** — Interactive snake-draft UI for the halfway point (Round 12)
- **Two-Half Scoring** — Separate driver ownership for H1 (Rounds 1-11) and H2 (Rounds 12-24)
- **Driver Substitutions** — Temporary driver replacements managed via a Google Sheets tab, with points automatically attributed to the owning player
- **Token Authentication** — Each player gets a unique token at draft start; picks are server-verified
- **Turn-Based RBAC** — Only the current picker can select a driver; enforced on both frontend and backend

### Web Interface
- **Dashboard** — F1-themed web UI with real-time leaderboard and score trends
- **Recent Results** — Session-by-session breakdown with driver points attribution
- **Race Calendar** — Full 2026 season schedule with session status tracking
- **Driver & Constructor Standings** — Live F1 championship tables
- **Draft Portal** — Interactive snake-draft interface with player identity, turn guards, and undo
- **WhatsApp Share** — One-click formatted standings for group chats

### Data Integrity
- **State Management** — Persistent tracking of sync status and scored sessions
- **Recovery System** — Automatic reconciliation of incomplete or missing session data
- **Error Handling** — Exponential backoff retry logic with rate limiting
- **Sheet Validation** — Automatic worksheet creation and data formatting
- **Durable Draft State** — Draft state persisted to Google Sheets (survives Render redeploys) with local disk fallback

## 📊 Players & H1 Draft

| Player | Driver 1 | Driver 2 | Driver 3 | Driver 4 | Driver 5 |
|--------|----------|----------|----------|----------|----------|
| Anup | Max Verstappen | Lewis Hamilton | Esteban Ocon | Franco Colapinto | Arvid Lindblad |
| Rohit | Kimi Antonelli | Lando Norris | Oliver Bearman | Alex Albon | Valtteri Bottas |
| Abhinav | Charles Leclerc | Oscar Piastri | Carlos Sainz | Fernando Alonso | Nico Hulkenberg |
| Prateik | George Russell | Isack Hadjar | Pierre Gasly | Gabriel Bortoleto | Liam Lawson |

## 🏁 Scoring System

| Session | Top Positions | Points |
|---------|---------------|--------|
| **Qualifying** | P1-P10 | 10, 9, 8, 7, 6, 5, 4, 3, 2, 1 |
| **Feature Race** | P1-P15 | 50, 40, 35, 30, 25, 20, 18, 16, 14, 12, 10, 9, 8, 7, 5 |
| **Sprint Race** | P1-P10 | 10, 9, 8, 7, 6, 5, 4, 3, 2, 1 |

**DNF / DNS / DSQ = 0 points**

## 🔄 Mid-Season Redraft

At the halfway point (Hungarian GP, Round 11), all 4 players redraft all 20 drivers using a **snake draft**:

```
Round 1: 1 → 2 → 3 → 4
Round 2: 4 → 3 → 2 → 1
Round 3: 1 → 2 → 3 → 4
Round 4: 4 → 3 → 2 → 1
Round 5: 1 → 2 → 3 → 4
```

Order is either randomized or manually set. The interactive draft UI is available at `/draft`.

### Authentication & Access Control

- Each player receives a **unique token** when the draft is started
- Players identify themselves on the draft page; tokens are stored in `localStorage`
- **Pick validation**: Backend verifies the token matches the current picker before accepting a pick
- **Undo**: Only the player who made the last pick can undo it (using their token). Admins can undo any pick via `X-Admin-Token` header.
- **Reset**: Admin-only — requires the `ADMIN_PASSWORD` environment variable, passed as `X-Admin-Token` header
- **Stale token recovery**: If a draft is reset, the UI detects invalid tokens and re-prompts for identity

### Persistence

Draft state is dual-written to **local disk** (`state/draft_state.json`) and **Google Sheets** ("Draft State" tab as a JSON blob). On startup, the app loads from Sheets first (survives Render's ephemeral disk), falling back to the local file.

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or higher
- Google account with access to Google Sheets API
- Google Sheets spreadsheet (will be created during setup)

### Installation

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd pakodis-f1-fantasy

# 2. Install dependencies
pip install -r requirements.txt
# OR using pyproject.toml
pip install -e .

# 3. Set up Google Sheets credentials (see below)

# 4. Configure environment variables
cp .env.example .env
# Edit .env with your configuration

# 5. Seed the spreadsheet with initial data
python -m src.seed_data

# 6. Start the server
python -m src.server
# Open http://localhost:8000
```

## 🔐 Google Sheets Setup

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "F1 Fantasy Draft")
3. Enable the **Google Sheets API** and **Google Drive API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Sheets API" and click "Enable"
   - Search for "Google Drive API" and click "Enable"

### Step 2: Create Service Account Credentials

1. Navigate to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Fill in the details:
   - Service account name: `f1-fantasy-service`
   - Service account ID: (auto-generated)
   - Click "Create and Continue"
4. Grant roles (optional): Skip this step, click "Continue"
5. Click "Done"

### Step 3: Generate JSON Key

1. Find your newly created service account in the credentials list
2. Click on the service account email
3. Go to the "Keys" tab
4. Click "Add Key" > "Create new key"
5. Select "JSON" format
6. Click "Create" — the JSON file will download automatically

### Step 4: Create Google Sheet

1. Go to [Google Sheets](https://sheets.google.com)
2. Create a new blank spreadsheet
3. Name it "F1 2026 Fantasy Draft" (or any name you prefer)
4. Copy the **Spreadsheet ID** from the URL:
   ```
   https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit
   ```
5. Share the spreadsheet with your service account email:
   - Click "Share" button
   - Paste the service account email (from your JSON file: `client_email`)
   - Give "Editor" permissions
   - Click "Send"

### Step 5: Configure Application

**For Local Development:**

1. Save the downloaded JSON file as `credentials.json` in the project root
2. Create a `.env` file:
   ```bash
   # Google Sheets Configuration
   GOOGLE_SHEETS_ID=your_spreadsheet_id_here
   GOOGLE_SHEETS_CREDENTIALS_FILE=./credentials.json
   
   # Optional: OpenF1 API Configuration
   OPENF1_BASE_URL=https://api.openf1.org/v1
   F1_SEASON_YEAR=2026
   
   # Sync Configuration
   SYNC_INTERVAL_MINUTES=60
   SYNC_LIVE_INTERVAL_SECONDS=120
   SYNC_TIMEZONE=Asia/Kolkata
   
   # Admin password for protected actions (reset, force sync)
   ADMIN_PASSWORD=your_secret_here
   
   # Season Configuration
   HALFWAY_ROUND=11
   ```

**For Production (Render, Heroku, etc.):**

1. Set environment variables in your hosting platform:
   ```bash
   GOOGLE_SHEETS_ID=your_spreadsheet_id_here
   GOOGLE_SHEETS_CREDENTIALS_JSON=<paste entire JSON file contents>
   ADMIN_PASSWORD=your_secret_here
   ```
2. To get the JSON as a single line:
   ```bash
   cat credentials.json | jq -c
   # Or manually: Remove all newlines and extra spaces
   ```

### Spreadsheet Structure

The seed script automatically creates these worksheets:

| Worksheet | Description |
|-----------|-------------|
| **Draft Picks H1** | First-half driver ownership (Rounds 1-11) |
| **Draft Picks H2** | Second-half driver ownership (Rounds 12+) |
| **Race Calendar** | 2026 F1 season schedule with 24 race weekends |
| **Session Results** | Detailed results for every scored session |
| **Leaderboard** | Current standings with H1/H2/Total breakdown |
| **Scoring Rules** | Points tables for reference |
| **Draft State** | JSON blob of live draft state (auto-created by draft engine) |
| **Draft Picks Log** | Human-readable pick log (auto-created by draft engine) |
| **Substitutions** | Temporary driver replacements (original → substitute, rounds, reason) |

## 🌐 API Endpoints

### Pages
- `GET /` — Main dashboard with leaderboard and score trends
- `GET /draft` — Interactive mid-season draft interface

### Status & Data
- `GET /api/status` — Leaderboard, recent sessions, last sync time
- `GET /api/drivers` — All 20 F1 drivers with team information
- `GET /api/calendar` — Race calendar with session statuses
- `GET /api/standings` — F1 driver and constructor championship standings
- `GET /api/share-text` — WhatsApp-formatted standings text

### Sync Operations
- `POST /api/sync` — Incremental sync (fetch only new sessions)
- `POST /api/sync/force` — Full sync (re-fetch all data from API)

### Draft Operations
- `GET /api/draft/status` — Current draft state and available drivers
- `POST /api/draft/claim-player` — Claim a player identity and receive auth token
- `POST /api/draft/start` — Initialize draft with player order (generates tokens)
- `POST /api/draft/pick` — Make a driver selection (requires `token`)
- `POST /api/draft/undo` — Undo the last pick (requires last picker's `token` or `X-Admin-Token`)
- `POST /api/draft/reset` — Reset the entire draft (requires `X-Admin-Token`)
- `POST /api/draft/finalize` — Save H2 picks to Google Sheets
- `POST /api/draft/simulate-pick` — Demo only: auto-pick a random driver for current picker

## 🏗️ Architecture

```
src/
├── config.py              — Environment-based configuration
├── server.py              — FastAPI web server with all endpoints
├── seed_data.py           — 2026 drivers, calendar, initial draft picks
├── substitutions.py       — Driver substitution logic and helpers
├── main.py                — CLI entry point
├── models/                — Data models
│   ├── driver.py          — Driver entity
│   ├── session.py         — Session with results
│   ├── player.py          — Player with driver ownership
│   └── draft_pick.py      — Draft pick tracking
├── scoring/               — Points calculation
│   ├── rules.py           — Scoring tables for each session type
│   └── calculator.py      — Points aggregation and leaderboard
├── data_sources/          — External APIs
│   └── openf1_api.py      — OpenF1 API client
├── draft/                 — Mid-season redraft system
│   ├── manager.py         — Draft state machine
│   └── order.py           — Snake draft order logic
├── sheets/                — Google Sheets integration
│   ├── client.py          — gspread wrapper with auth
│   ├── draft_state.py     — Durable draft state persistence (JSON blob in Sheets)
│   ├── players.py         — Read/write draft picks
│   ├── schedule.py        — Read/write race calendar
│   ├── results.py         — Read/write session results
│   ├── scores.py          — Write leaderboard
│   ├── scoring_rules.py   — Write scoring reference
│   ├── session_times.py   — Cached session times (avoids API calls on page load)
│   └── substitutions.py   — Read/write driver substitutions from Sheets
├── sync/                  — Data synchronization
│   ├── scheduler.py       — Adaptive sync scheduling
│   ├── state_manager.py   — Persistent state tracking
│   └── recovery.py        — Session reconciliation
└── utils/                 — Shared utilities
    ├── logger.py          — Logging configuration
    ├── rate_limiter.py    — API rate limiting
    └── retry.py           — Exponential backoff retry
```

## 🚢 Deploy to Render

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-repo-url>
   git push -u origin main
   ```

2. **Create Web Service on Render**
   - Go to [Render Dashboard](https://dashboard.render.com/)
   - Click "New" > "Web Service"
   - Connect your GitHub repository

3. **Configure Build Settings**
   - **Name**: f1-fantasy-draft
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn src.server:app --host 0.0.0.0 --port $PORT`

4. **Add Environment Variables**
   ```
   GOOGLE_SHEETS_ID=<your_spreadsheet_id>
   GOOGLE_SHEETS_CREDENTIALS_JSON=<your_service_account_json>
   ```

5. **Deploy** — Render will automatically build and deploy your app

## 📝 Development

### Running Tests
```bash
pytest
# OR with coverage
pytest --cov=src tests/
```

### Manual Sync
```bash
# Trigger incremental sync via API
curl -X POST http://localhost:8000/api/sync

# Force full sync
curl -X POST http://localhost:8000/api/sync/force
```

### View Logs
```bash
# Server logs in terminal
python -m src.server

# Check sync status
curl http://localhost:8000/api/status | python -m json.tool
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

MIT License — see LICENSE file for details

## 🙏 Acknowledgments

- [OpenF1 API](https://openf1.org) for free F1 data
- [FastAPI](https://fastapi.tiangolo.com/) for the web framework
- [gspread](https://docs.gspread.org/) for Google Sheets integration
- Formula 1 for the best sport in the world 🏎️
