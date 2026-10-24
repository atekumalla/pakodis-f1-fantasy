# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A FastAPI app for a 4-player F1 2026 fantasy draft league. Results come from the OpenF1 API (free, no key; ~3 req/s, 30 req/min). Google Sheets is the database. The UI is two static single-file pages: `static/index.html` (dashboard, Chart.js from CDN) and `static/draft.html` (mid-season snake draft). There is no frontend build step.

## Commands

```bash
pip install -r requirements.txt          # or: pip install -e .
cp .env.example .env                     # then set GOOGLE_SHEETS_ID + credentials
python -m src.server                     # dev server on http://localhost:8000
uvicorn src.server:app --host 0.0.0.0 --port $PORT   # how Render runs it (Procfile/render.yaml)
```

There is no `tests/` directory, even though `pyproject.toml` points pytest at one. The test-like files live in `scripts/` and are run directly:

```bash
python scripts/test_draft.py     # draft workflow against a mock state; no Sheets access
python scripts/test_startup.py   # connects to the REAL sheet and builds the leaderboard
```

There is no linter or formatter configured.

Without Sheets credentials the server still starts, running on seed data only, and the background scheduler is not started.

## Architecture

**Data flow / source of truth.** Google Sheets holds all historical results. On startup (the `lifespan` in `src/server.py`), the app loads players, calendar, session results, cached session times and substitutions from Sheets into the module-level `_app_state` dict, without calling the API. Every endpoint reads from `_app_state`.

- **Incremental sync** (`_do_sync` in `src/server.py`) fetches only sessions not already in Sheets, merges them in memory, then **overwrites** the Results and Leaderboard tabs with the full set. `SyncScheduler` (APScheduler) runs it every `SYNC_INTERVAL_MINUTES`, or every `SYNC_LIVE_INTERVAL_SECONDS` while a session is `IN_PROGRESS`.
- **Force sync** (`/api/sync/force`, admin-only) re-fetches everything from the API. It is expensive and rate-limited separately.
- **Session identity is `(round_number, session_type)`, not `session_key`.** Sessions read back from Sheets have synthetic keys (`round*100 + type`, always < 3000). Real OpenF1 keys are larger. Dedupe and merge logic depends on this, so preserve it when touching sync or `src/sheets/results.py`.
- Sessions with empty results are deliberately left out of the "already have" set so later syncs can fill them in.

**Scoring** (`src/scoring/`). `rules.py` holds the points tables, and `ScoringCalculator` turns them into per-player totals.
- **Two halves.** Each session has a `half` (H1/H2) derived from `HALFWAY_ROUND` (default 11: rounds 1–11 are H1, 12+ are H2). Each player has separate H1 and H2 driver lists (`DraftPlayer.drivers_for_half`).
- **Substitutions** (`src/substitutions.py`): a substitute's points in the listed rounds go to the player who owns the original driver. The "Substitutions" sheet tab is the source of truth, and `ACTIVE_SUBSTITUTIONS` in code is only a fallback.
- **Driver names** are matched through `normalize_driver_name` (lowercase plus an alias map, e.g. "Alex Albon" → "Alexander Albon"). If a driver's points come out as 0 because of a name mismatch, add an alias there.

**Seed data** (`src/seed_data.py`): the hardcoded 2026 drivers, players, H1 picks and `CALENDAR_2026`. The calendar is curated by hand (round numbers must match live scoring rounds, and cancelled races are flagged). The calendar endpoints and session-time refresh read from it.

**Mid-season draft** (`src/draft/`). `DraftManager` is a snake-draft state machine.
- Its state is dual-written to `state/draft_state.json` and to the "Draft State" sheet tab as a JSON blob. On startup it loads from Sheets first, because Render's disk is ephemeral.
- Each player gets a token at draft start, and the backend checks it against the current picker. Admin actions use the `X-Admin-Token` header compared against `ADMIN_PASSWORD` (`_require_admin`).
- `/api/draft/finalize` writes the H2 picks to Sheets.
- `?demo=true` uses a separate `DraftManager` with its own state file, optionally persisted to `DEMO_GOOGLE_SHEETS_ID`. It must never touch the real league sheet.

**Sheets layer** (`src/sheets/`): one module per worksheet tab, all built on `SheetsClient` (gspread). Credentials come from `GOOGLE_SHEETS_CREDENTIALS_JSON` (single-line JSON, used in production) or from `GOOGLE_SHEETS_CREDENTIALS_FILE` (local).

## Cautions

- `python -m src.seed_data` re-seeds the **whole** spreadsheet: it rewrites H1 picks and scoring rules and resets the leaderboard. Do not run it mid-season against the real sheet. For calendar sprint flags, use `scripts/sync_calendar_to_sheet.py`, which touches only that tab.
- Several scripts (`emergency_clean_sheets.py`, `fix_duplicate_sessions.py`, `trigger_force_sync.py`) mutate the production sheet or the deployed service.
- `.env`, `credentials.json` and the service-account JSON in the repo root are real secrets and are gitignored. Never commit them.

## Deployment

Render web service (free plan, auto-deploys from `main`). Config is in `render.yaml`. `DEPLOYMENT.md` documents creating the service manually in the dashboard, so dashboard env vars (e.g. `PYTHON_VERSION`) may override `render.yaml`. Secrets (`GOOGLE_SHEETS_ID`, `GOOGLE_SHEETS_CREDENTIALS_JSON`, `ADMIN_PASSWORD`) are set in the dashboard.
