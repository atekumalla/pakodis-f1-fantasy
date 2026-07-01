"""Seed the Google Sheet with F1 2026 season data.

Run this once to set up the spreadsheet with:
  1. Draft picks (H1 — initial driver ownership)
  2. Race calendar (all 24 rounds)
  3. Scoring rules reference
  4. Empty leaderboard

Usage:
    python -m src.seed_data
"""

from __future__ import annotations

import logging
from datetime import date

from src.config import Config, HALFWAY_ROUND
from src.models.driver import Driver
from src.models.player import DraftPlayer
from src.models.session import RaceWeekend
from src.scoring.rules import DEFAULT_RULES
from src.scoring.calculator import ScoringCalculator
from src.sheets.client import SheetsClient
from src.sheets.players import write_draft_picks_h1
from src.sheets.schedule import write_calendar
from src.sheets.scores import write_leaderboard
from src.sheets.scoring_rules import write_scoring_rules
from src.utils.logger import setup_logging

logger = logging.getLogger(__name__)


# ==============================================================================
# 2026 F1 DRIVER GRID
# ==============================================================================

# Team colors from F1 official branding
TEAM_COLORS = {
    "Red Bull Racing": "3671C6",
    "McLaren": "FF8000",
    "Ferrari": "E80020",
    "Mercedes": "27F4D2",
    "Aston Martin": "229971",
    "Alpine": "0093CC",
    "Williams": "64C4FF",
    "Racing Bulls": "6692FF",
    "Haas": "B6BABD",
    "Audi": "FF1E00",
    "Cadillac": "000000",
}

# Country codes for flag emojis (driver countries)
COUNTRY_FLAGS = {
    "NED": "🇳🇱",  # Netherlands
    "NZL": "🇳🇿",  # New Zealand  
    "GBR": "🇬🇧",  # Great Britain
    "AUS": "🇦🇺",  # Australia
    "MON": "🇲🇨",  # Monaco
    "ESP": "🇪🇸",  # Spain
    "ITA": "🇮🇹",  # Italy
    "FRA": "🇫🇷",  # France
    "ARG": "🇦🇷",  # Argentina
    "THA": "🇹🇭",  # Thailand
    "FIN": "🇫🇮",  # Finland
    "GER": "🇩🇪",  # Germany
    "BRA": "🇧🇷",  # Brazil
    "MEX": "🇲🇽",  # Mexico
    "CAN": "🇨🇦",  # Canada
}

# Country name to flag emojis (for race locations)
RACE_COUNTRY_FLAGS = {
    "Australia": "🇦🇺",
    "China": "🇨🇳",
    "Japan": "🇯🇵",
    "Bahrain": "🇧🇭",
    "Saudi Arabia": "🇸🇦",
    "United States": "🇺🇸",
    "Italy": "🇮🇹",
    "Monaco": "🇲🇨",
    "Spain": "🇪🇸",
    "Canada": "🇨🇦",
    "Austria": "🇦🇹",
    "United Kingdom": "🇬🇧",
    "Belgium": "🇧🇪",
    "Hungary": "🇭🇺",
    "Netherlands": "🇳🇱",
    "Azerbaijan": "🇦🇿",
    "Singapore": "🇸🇬",
    "Mexico": "🇲🇽",
    "Brazil": "🇧🇷",
    "Qatar": "🇶🇦",
    "United Arab Emirates": "🇦🇪",
}

DRIVERS_2026: list[dict] = [
    {"number": 1,   "name": "Max Verstappen",      "team": "Red Bull Racing",   "acronym": "VER", "country": "NED", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/M/MAXVER01_Max_Verstappen/maxver01.png.transform/1col/image.png"},
    {"number": 6,   "name": "Isack Hadjar",         "team": "Red Bull Racing",   "acronym": "HAD", "country": "FRA", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/I/ISAHAD01_Isack_Hadjar/isahad01.png.transform/1col/image.png"},
    {"number": 4,   "name": "Lando Norris",         "team": "McLaren",           "acronym": "NOR", "country": "GBR", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/L/LANNOR01_Lando_Norris/lannor01.png.transform/1col/image.png"},
    {"number": 81,  "name": "Oscar Piastri",        "team": "McLaren",           "acronym": "PIA", "country": "AUS", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/O/OSCPIA01_Oscar_Piastri/oscpia01.png.transform/1col/image.png"},
    {"number": 16,  "name": "Charles Leclerc",      "team": "Ferrari",           "acronym": "LEC", "country": "MON", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/C/CHALEC01_Charles_Leclerc/chalec01.png.transform/1col/image.png"},
    {"number": 44,  "name": "Lewis Hamilton",       "team": "Ferrari",           "acronym": "HAM", "country": "GBR", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/L/LEWHAM01_Lewis_Hamilton/lewham01.png.transform/1col/image.png"},
    {"number": 63,  "name": "George Russell",       "team": "Mercedes",          "acronym": "RUS", "country": "GBR", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/G/GEORUS01_George_Russell/georus01.png.transform/1col/image.png"},
    {"number": 12,  "name": "Kimi Antonelli",       "team": "Mercedes",          "acronym": "ANT", "country": "ITA", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/K/ANDANT01_Kimi_Antonelli/andant01.png.transform/1col/image.png"},
    {"number": 14,  "name": "Fernando Alonso",      "team": "Aston Martin",      "acronym": "ALO", "country": "ESP", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/F/FERALO01_Fernando_Alonso/feralo01.png.transform/1col/image.png"},
    {"number": 18,  "name": "Lance Stroll",         "team": "Aston Martin",      "acronym": "STR", "country": "CAN", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/L/LANSTR01_Lance_Stroll/lanstr01.png.transform/1col/image.png"},
    {"number": 10,  "name": "Pierre Gasly",         "team": "Alpine",            "acronym": "GAS", "country": "FRA", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/P/PIEGAS01_Pierre_Gasly/piegas01.png.transform/1col/image.png"},
    {"number": 43,  "name": "Franco Colapinto",     "team": "Alpine",            "acronym": "COL", "country": "ARG", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/F/FRACOL01_Franco_Colapinto/fracol01.png.transform/1col/image.png"},
    {"number": 55,  "name": "Carlos Sainz",         "team": "Williams",          "acronym": "SAI", "country": "ESP", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/C/CARSAI01_Carlos_Sainz/carsai01.png.transform/1col/image.png"},
    {"number": 23,  "name": "Alex Albon",           "team": "Williams",          "acronym": "ALB", "country": "THA", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/A/ALEALB01_Alexander_Albon/alealb01.png.transform/1col/image.png"},
    {"number": 30,  "name": "Liam Lawson",          "team": "Racing Bulls",      "acronym": "LAW", "country": "NZL", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/L/LIALAW01_Liam_Lawson/lialaw01.png.transform/1col/image.png"},
    {"number": 41,  "name": "Arvid Lindblad",       "team": "Racing Bulls",      "acronym": "LIN", "country": "GBR", "headshot_url": "https://cdn.racingnews365.com/production/Riders/Lindblad/driver_avatar_al_rac_2026.png?v=1772639778&width=240&height=280&format=png&crop=393%2C458%2C32%2C0"},
    {"number": 31,  "name": "Esteban Ocon",         "team": "Haas",              "acronym": "OCO", "country": "FRA", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/E/ESTOCO01_Esteban_Ocon/estoco01.png.transform/1col/image.png"},
    {"number": 87,  "name": "Oliver Bearman",       "team": "Haas",              "acronym": "BEA", "country": "GBR", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/O/OLIBEA01_Oliver_Bearman/olibea01.png.transform/1col/image.png"},
    {"number": 27,  "name": "Nico Hulkenberg",      "team": "Audi",              "acronym": "HUL", "country": "GER", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/N/NICHUL01_Nico_Hulkenberg/nichul01.png.transform/1col/image.png"},
    {"number": 50,  "name": "Gabriel Bortoleto",    "team": "Audi",              "acronym": "BOR", "country": "BRA", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/G/GABBOR01_Gabriel_Bortoleto/gabbor01.png.transform/1col/image.png"},
    {"number": 77,  "name": "Valtteri Bottas",      "team": "Cadillac",          "acronym": "BOT", "country": "FIN", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/V/VALBOT01_Valtteri_Bottas/valbot01.png.transform/1col/image.png"},
    {"number": 11,  "name": "Sergio Perez",         "team": "Cadillac",          "acronym": "PER", "country": "MEX", "headshot_url": "https://media.formula1.com/content/dam/fom-website/drivers/S/SERPER01_Sergio_Perez/serper01.png.transform/1col/image.png"},
]


def get_all_driver_names() -> list[str]:
    """Return all 20 driver names."""
    return [d["name"] for d in DRIVERS_2026]


def get_driver_by_name(name: str) -> dict | None:
    """Find a driver by name (case-insensitive partial match)."""
    name_lower = name.lower()
    for d in DRIVERS_2026:
        if name_lower in d["name"].lower():
            return d
    return None


# ==============================================================================
# INITIAL DRAFT PICKS (H1)
# ==============================================================================

DRAFT_PICKS_H1: dict[str, list[str]] = {
    "Anup": [
        "Max Verstappen",
        "Lewis Hamilton",
        "Esteban Ocon",
        "Franco Colapinto",
        "Arvid Lindblad",
    ],
    "Rohit": [
        "Kimi Antonelli",
        "Lando Norris",
        "Oliver Bearman",
        "Alex Albon",
        "Valtteri Bottas",
    ],
    "Abhinav": [
        "Charles Leclerc",
        "Oscar Piastri",
        "Carlos Sainz",
        "Fernando Alonso",
        "Nico Hulkenberg",
    ],
    "Prateik": [
        "George Russell",
        "Isack Hadjar",
        "Pierre Gasly",
        "Gabriel Bortoleto",
        "Liam Lawson",
    ],
}

PLAYER_NAMES = list(DRAFT_PICKS_H1.keys())


def get_initial_players() -> list[DraftPlayer]:
    """Create DraftPlayer objects from the initial H1 picks."""
    return [
        DraftPlayer(name=name, drivers_h1=drivers)
        for name, drivers in DRAFT_PICKS_H1.items()
    ]


# ==============================================================================
# 2026 RACE CALENDAR (24 rounds, British GP = Round 12 = halfway)
# ==============================================================================

CALENDAR_2026: list[dict] = [
    {"round": 1,  "name": "Australian Grand Prix",      "circuit": "Albert Park",                    "country": "Australia",       "date": "2026-03-15", "sprint": False},
    {"round": 2,  "name": "Chinese Grand Prix",         "circuit": "Shanghai International Circuit", "country": "China",           "date": "2026-03-29", "sprint": True},
    {"round": 3,  "name": "Japanese Grand Prix",        "circuit": "Suzuka International Racing Course", "country": "Japan",       "date": "2026-04-05", "sprint": False},
    {"round": 4,  "name": "Bahrain Grand Prix",         "circuit": "Bahrain International Circuit",  "country": "Bahrain",         "date": "2026-04-19", "sprint": False},
    {"round": 5,  "name": "Saudi Arabian Grand Prix",   "circuit": "Jeddah Corniche Circuit",        "country": "Saudi Arabia",    "date": "2026-04-26", "sprint": False},
    {"round": 6,  "name": "Miami Grand Prix",           "circuit": "Miami International Autodrome",  "country": "United States",   "date": "2026-05-03", "sprint": True},
    {"round": 7,  "name": "Emilia Romagna Grand Prix",  "circuit": "Autodromo Enzo e Dino Ferrari",  "country": "Italy",           "date": "2026-05-17", "sprint": False},
    {"round": 8,  "name": "Monaco Grand Prix",          "circuit": "Circuit de Monaco",              "country": "Monaco",          "date": "2026-05-24", "sprint": False},
    {"round": 9,  "name": "Spanish Grand Prix",         "circuit": "Circuit de Barcelona-Catalunya", "country": "Spain",           "date": "2026-06-07", "sprint": False},
    {"round": 10, "name": "Canadian Grand Prix",        "circuit": "Circuit Gilles Villeneuve",      "country": "Canada",          "date": "2026-06-14", "sprint": False},
    {"round": 11, "name": "Austrian Grand Prix",        "circuit": "Red Bull Ring",                  "country": "Austria",         "date": "2026-06-28", "sprint": True},
    {"round": 12, "name": "British Grand Prix",         "circuit": "Silverstone Circuit",            "country": "United Kingdom",  "date": "2026-07-05", "sprint": False},
    {"round": 13, "name": "Belgian Grand Prix",         "circuit": "Circuit de Spa-Francorchamps",   "country": "Belgium",         "date": "2026-07-19", "sprint": False},
    {"round": 14, "name": "Hungarian Grand Prix",       "circuit": "Hungaroring",                    "country": "Hungary",         "date": "2026-07-26", "sprint": False},
    {"round": 15, "name": "Dutch Grand Prix",           "circuit": "Circuit Zandvoort",              "country": "Netherlands",     "date": "2026-08-23", "sprint": False},
    {"round": 16, "name": "Italian Grand Prix",         "circuit": "Autodromo Nazionale Monza",      "country": "Italy",           "date": "2026-09-06", "sprint": False},
    {"round": 17, "name": "Spanish Grand Prix",         "circuit": "Madrid Street Circuit",          "country": "Spain",           "date": "2026-09-13", "sprint": False},
    {"round": 18, "name": "Azerbaijan Grand Prix",      "circuit": "Baku City Circuit",              "country": "Azerbaijan",      "date": "2026-09-26", "sprint": True},
    {"round": 19, "name": "Singapore Grand Prix",       "circuit": "Marina Bay Street Circuit",      "country": "Singapore",       "date": "2026-10-11", "sprint": False},
    {"round": 20, "name": "United States Grand Prix",   "circuit": "Circuit of the Americas",        "country": "United States",   "date": "2026-10-25", "sprint": True},
    {"round": 21, "name": "Mexico City Grand Prix",     "circuit": "Autodromo Hermanos Rodriguez",   "country": "Mexico",          "date": "2026-11-01", "sprint": False},
    {"round": 22, "name": "São Paulo Grand Prix",       "circuit": "Autodromo Jose Carlos Pace",     "country": "Brazil",          "date": "2026-11-08", "sprint": True},
    {"round": 23, "name": "Las Vegas Grand Prix",       "circuit": "Las Vegas Strip Circuit",        "country": "United States",   "date": "2026-11-21", "sprint": False},
    {"round": 24, "name": "Qatar Grand Prix",           "circuit": "Lusail International Circuit",   "country": "Qatar",           "date": "2026-11-29", "sprint": False},
    {"round": 25, "name": "Abu Dhabi Grand Prix",       "circuit": "Yas Marina Circuit",             "country": "United Arab Emirates", "date": "2026-12-06", "sprint": False},
]


# Pre-seeded session times (PST) for upcoming races - will be overwritten by API when available
# Format: race name -> list of sessions with times
PRESEEDED_SESSION_TIMES = {
    "British Grand Prix": {
        "date": "2026-07-05",
        "sessions": [
            {"name": "Practice 1", "day_offset": -2, "time": "05:30"},  # Friday
            {"name": "Practice 2", "day_offset": -2, "time": "09:00"},
            {"name": "Practice 3", "day_offset": -1, "time": "05:30"},  # Saturday
            {"name": "Qualifying", "day_offset": -1, "time": "09:00"},
            {"name": "Race", "day_offset": 0, "time": "07:00"},  # Sunday (race day)
        ]
    },
    "Belgian Grand Prix": {
        "date": "2026-07-19",
        "sessions": [
            {"name": "Practice 1", "day_offset": -2, "time": "05:30"},
            {"name": "Practice 2", "day_offset": -2, "time": "09:00"},
            {"name": "Practice 3", "day_offset": -1, "time": "04:30"},
            {"name": "Qualifying", "day_offset": -1, "time": "08:00"},
            {"name": "Race", "day_offset": 0, "time": "06:00"},
        ]
    },
    "Hungarian Grand Prix": {
        "date": "2026-07-26",
        "sessions": [
            {"name": "Practice 1", "day_offset": -2, "time": "05:30"},
            {"name": "Practice 2", "day_offset": -2, "time": "09:00"},
            {"name": "Practice 3", "day_offset": -1, "time": "04:30"},
            {"name": "Qualifying", "day_offset": -1, "time": "08:00"},
            {"name": "Race", "day_offset": 0, "time": "06:00"},
        ]
    },
    "Dutch Grand Prix": {
        "date": "2026-08-23",
        "sessions": [
            {"name": "Practice 1", "day_offset": -2, "time": "04:30"},
            {"name": "Practice 2", "day_offset": -2, "time": "08:00"},
            {"name": "Practice 3", "day_offset": -1, "time": "03:30"},
            {"name": "Qualifying", "day_offset": -1, "time": "07:00"},
            {"name": "Race", "day_offset": 0, "time": "06:00"},
        ]
    },
    "Italian Grand Prix": {
        "date": "2026-09-06",
        "sessions": [
            {"name": "Practice 1", "day_offset": -2, "time": "05:30"},
            {"name": "Practice 2", "day_offset": -2, "time": "09:00"},
            {"name": "Practice 3", "day_offset": -1, "time": "04:30"},
            {"name": "Qualifying", "day_offset": -1, "time": "08:00"},
            {"name": "Race", "day_offset": 0, "time": "06:00"},
        ]
    },
    "Spanish Grand Prix": {
        "date": "2026-09-13",
        "sessions": [
            {"name": "Practice 1", "day_offset": -2, "time": "05:30"},
            {"name": "Practice 2", "day_offset": -2, "time": "09:00"},
            {"name": "Practice 3", "day_offset": -1, "time": "04:30"},
            {"name": "Qualifying", "day_offset": -1, "time": "08:00"},
            {"name": "Race", "day_offset": 0, "time": "06:00"},
        ]
    },
    "Azerbaijan Grand Prix": {
        "date": "2026-09-26",
        "sessions": [
            {"name": "Practice 1", "day_offset": -2, "time": "04:30"},
            {"name": "Sprint Shootout", "day_offset": -1, "time": "04:30"},
            {"name": "Sprint", "day_offset": -1, "time": "08:30"},
            {"name": "Qualifying", "day_offset": -2, "time": "08:00"},
            {"name": "Race", "day_offset": 0, "time": "04:00"},
        ]
    },
    "Singapore Grand Prix": {
        "date": "2026-10-11",
        "sessions": [
            {"name": "Practice 1", "day_offset": -2, "time": "01:30"},
            {"name": "Practice 2", "day_offset": -2, "time": "05:00"},
            {"name": "Practice 3", "day_offset": -1, "time": "01:30"},
            {"name": "Qualifying", "day_offset": -1, "time": "05:00"},
            {"name": "Race", "day_offset": 0, "time": "05:00"},
        ]
    },
    "United States Grand Prix": {
        "date": "2026-10-25",
        "sessions": [
            {"name": "Practice 1", "day_offset": -2, "time": "10:30"},
            {"name": "Sprint Shootout", "day_offset": -1, "time": "10:30"},
            {"name": "Sprint", "day_offset": -1, "time": "14:00"},
            {"name": "Qualifying", "day_offset": -2, "time": "14:00"},
            {"name": "Race", "day_offset": 0, "time": "13:00"},
        ]
    },
    "Mexico City Grand Prix": {
        "date": "2026-11-01",
        "sessions": [
            {"name": "Practice 1", "day_offset": -2, "time": "10:30"},
            {"name": "Practice 2", "day_offset": -2, "time": "14:00"},
            {"name": "Practice 3", "day_offset": -1, "time": "09:30"},
            {"name": "Qualifying", "day_offset": -1, "time": "13:00"},
            {"name": "Race", "day_offset": 0, "time": "12:00"},
        ]
    },
    "São Paulo Grand Prix": {
        "date": "2026-11-08",
        "sessions": [
            {"name": "Practice 1", "day_offset": -2, "time": "08:30"},
            {"name": "Sprint Shootout", "day_offset": -1, "time": "05:30"},
            {"name": "Sprint", "day_offset": -1, "time": "09:00"},
            {"name": "Qualifying", "day_offset": -2, "time": "12:00"},
            {"name": "Race", "day_offset": 0, "time": "09:00"},
        ]
    },
    "Las Vegas Grand Prix": {
        "date": "2026-11-21",
        "sessions": [
            {"name": "Practice 1", "day_offset": -2, "time": "17:30"},
            {"name": "Practice 2", "day_offset": -2, "time": "21:00"},
            {"name": "Practice 3", "day_offset": -1, "time": "17:30"},
            {"name": "Qualifying", "day_offset": -1, "time": "21:00"},
            {"name": "Race", "day_offset": 0, "time": "20:00"},
        ]
    },
    "Qatar Grand Prix": {
        "date": "2026-11-29",
        "sessions": [
            {"name": "Practice 1", "day_offset": -2, "time": "05:30"},
            {"name": "Practice 2", "day_offset": -2, "time": "09:00"},
            {"name": "Practice 3", "day_offset": -1, "time": "06:30"},
            {"name": "Qualifying", "day_offset": -1, "time": "10:00"},
            {"name": "Race", "day_offset": 0, "time": "08:00"},
        ]
    },
    "Abu Dhabi Grand Prix": {
        "date": "2026-12-06",
        "sessions": [
            {"name": "Practice 1", "day_offset": -2, "time": "01:30"},
            {"name": "Practice 2", "day_offset": -2, "time": "05:00"},
            {"name": "Practice 3", "day_offset": -1, "time": "02:30"},
            {"name": "Qualifying", "day_offset": -1, "time": "06:00"},
            {"name": "Race", "day_offset": 0, "time": "05:00"},
        ]
    },
}


def get_race_weekends() -> list[RaceWeekend]:
    """Fetch race calendar from the OpenF1 API.
    
    Falls back to hardcoded CALENDAR_2026 if API is unavailable.
    Excludes canceled races from the list.
    """
    from src.data_sources.openf1_api import OpenF1API
    
    try:
        api = OpenF1API()
        weekends = api.fetch_race_calendar(include_cancelled=False)
        if weekends:
            logger.info(f"Fetched {len(weekends)} active races from OpenF1 API")
            return weekends
    except Exception as e:
        logger.warning(f"Failed to fetch calendar from API: {e}")
    
    # Fallback to hardcoded calendar (filter out known canceled races)
    logger.info("Using fallback hardcoded calendar")
    active_races = [r for r in CALENDAR_2026 if r["name"] not in ("Bahrain Grand Prix", "Saudi Arabian Grand Prix")]
    
    # Renumber rounds after filtering
    return [
        RaceWeekend(
            meeting_key=i * 1000,  # placeholder
            round_number=i,
            name=r["name"],
            circuit=r["circuit"],
            country=r["country"],
            race_date=date.fromisoformat(r["date"]),
            has_sprint=r["sprint"],
        )
        for i, r in enumerate(active_races, start=1)
    ]


def get_halfway_round() -> int:
    """Get the halfway round number dynamically.
    
    Returns half of the active races (e.g., 11 for 22 races).
    Falls back to HALFWAY_ROUND constant if API unavailable.
    """
    weekends = get_race_weekends()
    return len(weekends) // 2


# ==============================================================================
# SEED SPREADSHEET
# ==============================================================================

def seed_spreadsheet():
    """Main entry point: seed the Google Sheet with initial F1 2026 data."""
    setup_logging()
    logger.info("=" * 60)
    logger.info("🏎️  F1 2026 Fantasy Draft — Seeding Spreadsheet")
    logger.info("=" * 60)

    errors = Config.validate()
    if errors:
        for err in errors:
            logger.error(f"Config error: {err}")
        raise SystemExit(1)

    client = SheetsClient()
    calculator = ScoringCalculator(DEFAULT_RULES)
    players = get_initial_players()
    weekends = get_race_weekends()

    # 1. Write draft picks (H1)
    logger.info("Writing H1 draft picks...")
    write_draft_picks_h1(client, players)

    # 2. Write race calendar
    logger.info("Writing race calendar...")
    write_calendar(client, weekends)

    # 3. Write scoring rules
    logger.info("Writing scoring rules...")
    write_scoring_rules(client)

    # 4. Write empty leaderboard
    logger.info("Writing initial leaderboard...")
    write_leaderboard(client, players, [], calculator)

    logger.info("=" * 60)
    logger.info("✅ Spreadsheet seeded successfully!")
    logger.info(f"   Players: {', '.join(p.name for p in players)}")
    logger.info(f"   Races: {len(weekends)} active")
    halfway = get_halfway_round()
    halfway_race = weekends[halfway - 1].name if halfway <= len(weekends) else "N/A"
    logger.info(f"   Halfway: Round {halfway} ({halfway_race})")
    logger.info("=" * 60)


if __name__ == "__main__":
    seed_spreadsheet()
