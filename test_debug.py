"""Debug: check why player points are 0 despite sessions having results."""
import sys
sys.path.insert(0, ".")

from src.sheets.client import SheetsClient
from src.sheets.results import read_results
from src.scoring.calculator import ScoringCalculator
from src.scoring.rules import DEFAULT_RULES
from src.sheets.players import read_draft_picks

client = SheetsClient()
players = read_draft_picks(client)
sessions = read_results(client)

print("=== PLAYERS & THEIR DRIVERS ===")
for p in players:
    print(f"  {p.name}: {p.drivers_h1}")

print("\n=== DRIVER NAMES IN SESSION RESULTS ===")
session = sessions[1]  # Race session
driver_names = [r.driver_name for r in session.results[:10]]
print(f"  {session.grand_prix} {session.session_name}:")
for r in session.results[:10]:
    print(f"    P{r.position}: {r.driver_name} (#{r.driver_number})")

# Test scoring directly
calculator = ScoringCalculator(DEFAULT_RULES)
pts = calculator.calculate_session_points(session)
print(f"\n=== SESSION POINTS (top 10) ===")
for name, p in sorted(pts.items(), key=lambda x: -x[1])[:10]:
    print(f"  {name}: {p}")

# Check player scoring
print(f"\n=== PLAYER SESSION POINTS ===")
for player in players:
    player_pts = calculator.calculate_player_session_points(player, session)
    print(f"  {player.name}: {player_pts} (drivers: {player.drivers_h1})")
