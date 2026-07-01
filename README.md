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
- **Two-Half Scoring** — Separate driver ownership for H1 (Rounds 1-12) and H2 (Rounds 13-24)

### Web Interface
- **Dashboard** — F1-themed web UI with real-time leaderboard and score trends
- **Recent Results** — Session-by-session breakdown with driver points attribution
- **Race Calendar** — Full 2026 season schedule with session status tracking
- **Driver & Constructor Standings** — Live F1 championship tables
- **Draft Portal** — Interactive snake-draft interface with undo/reset functionality
- **WhatsApp Share** — One-click formatted standings for group chats

### Data Integrity
- **State Management** — Persistent tracking of sync status and scored sessions
- **Recovery System** — Automatic reconciliation of incomplete or missing session data
- **Error Handling** — Exponential backoff retry logic with rate limiting
- **Sheet Validation** — Automatic worksheet creation and data formatting

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

At the halfway point (British GP, Round 12), all 4 players redraft all 20 drivers using a **snake draft**:

```
Round 1: 1 → 2 → 3 → 4
Round 2: 4 → 3 → 2 → 1
Round 3: 1 → 2 → 3 → 4
Round 4: 4 → 3 → 2 → 1
Round 5: 1 → 2 → 3 → 4
```

Order is either randomized or manually set. The interactive draft UI is available at `/draft`.

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
   
   # Season Configuration
   HALFWAY_ROUND=12
   ```

**For Production (Render, Heroku, etc.):**

1. Set environment variables in your hosting platform:
   ```bash
   GOOGLE_SHEETS_ID=your_spreadsheet_id_here
   GOOGLE_SHEETS_CREDENTIALS_JSON=<paste entire JSON file contents>
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
| **Draft Picks H1** | First-half driver ownership (Rounds 1-12) |
| **Draft Picks H2** | Second-half driver ownership (Rounds 13-24) |
| **Race Calendar** | 2026 F1 season schedule with 24 race weekends |
| **Session Results** | Detailed results for every scored session |
| **Leaderboard** | Current standings with H1/H2/Total breakdown |
| **Scoring Rules** | Points tables for reference |

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
- `POST /api/draft/start` — Initialize draft with player order
- `POST /api/draft/pick` — Make a driver selection
- `POST /api/draft/undo` — Undo the last pick
- `POST /api/draft/reset` — Reset the entire draft
- `POST /api/draft/finalize` — Save H2 picks to Google Sheets

## 🏗️ Architecture

```
src/
├── config.py              — Environment-based configuration
├── server.py              — FastAPI web server with all endpoints
├── seed_data.py           — 2026 drivers, calendar, initial draft picks
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
│   ├── players.py         — Read/write draft picks
│   ├── schedule.py        — Read/write race calendar
│   ├── results.py         — Read/write session results
│   ├── scores.py          — Write leaderboard
│   └── scoring_rules.py   — Write scoring reference
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
