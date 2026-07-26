"""Quick test: verify sessions load from sheets on startup."""
import sys
sys.path.insert(0, ".")

from src.sheets.client import SheetsClient
from src.sheets.results import read_results
from src.scoring.calculator import ScoringCalculator
from src.scoring.rules import DEFAULT_RULES
from src.sheets.players import read_draft_picks

client = SheetsClient()
print("✅ Connected to Google Sheets")

players = read_draft_picks(client)
print(f"✅ Loaded {len(players)} players")

sessions = read_results(client)
print(f"✅ Loaded {len(sessions)} sessions from sheet")

if sessions:
    print(f"\n   Sample sessions:")
    for s in sessions[:5]:
        print(f"     Round {s.round_number}: {s.grand_prix} {s.session_name} — {len(s.results)} results")

    calculator = ScoringCalculator(DEFAULT_RULES)
    leaderboard = calculator.build_leaderboard(players, sessions)
    print(f"\n✅ Leaderboard ({len(leaderboard)} entries):")
    for entry in leaderboard:
        print(f"     {entry['name']}: {entry['total']} pts")
else:
    print("⚠️  No sessions in sheet — need a force sync first")
