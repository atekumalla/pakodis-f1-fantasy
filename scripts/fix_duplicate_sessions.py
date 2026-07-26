#!/usr/bin/env python3
"""
Diagnostic and fix script for duplicate sessions in Google Sheets.

This script will:
1. Read all session results from the sheet
2. Detect duplicate sessions (same session_key appearing multiple times)
3. Show stats about duplicates
4. Optionally fix by removing duplicates and re-writing
"""

import sys
from collections import Counter, defaultdict

from src.sheets.client import SheetsClient
from src.sheets.results import read_results, write_results, WORKSHEET_TITLE
from src.scoring.calculator import ScoringCalculator
from src.scoring.rules import DEFAULT_RULES


def analyze_duplicates():
    """Analyze the Google Sheet for duplicate sessions."""
    print("🔍 Analyzing Google Sheets for duplicate sessions...")
    print()
    
    client = SheetsClient()
    
    # Read raw sheet data
    data = client.read_all_values(WORKSHEET_TITLE)
    
    if not data or len(data) < 2:
        print("❌ No data found in Session Results sheet")
        return
    
    print(f"📊 Total rows in sheet: {len(data) - 1} (excluding header)")
    print()
    
    # Group by session key (date + round + grand_prix + session)
    session_groups = defaultdict(list)
    
    for i, row in enumerate(data[1:], start=2):  # Start at row 2 (after header)
        if not row or len(row) < 6:
            continue
        
        try:
            # Key: (date, round, grand_prix, session)
            key = (row[0], row[1], row[2], row[3])
            session_groups[key].append((i, row))
        except Exception as e:
            print(f"⚠️  Warning: Failed to parse row {i}: {e}")
    
    print(f"📅 Unique sessions found: {len(session_groups)}")
    print()
    
    # Find duplicates
    duplicates = {k: v for k, v in session_groups.items() if len(v) > 20}
    
    if not duplicates:
        print("✅ No duplicate sessions found! All clear.")
        return
    
    print(f"⚠️  DUPLICATES FOUND: {len(duplicates)} sessions have more than 20 drivers")
    print()
    
    # Show details
    for (date, round_num, gp, session), rows in sorted(duplicates.items()):
        print(f"🏁 {gp} - {session} (Round {round_num}, {date})")
        print(f"   Found {len(rows)} driver entries (expected ~20)")
        
        # Count unique drivers
        drivers = [row[5] for _, row in rows if len(row) > 5]
        driver_counts = Counter(drivers)
        duped_drivers = {d: c for d, c in driver_counts.items() if c > 1}
        
        if duped_drivers:
            print(f"   Duplicated drivers:")
            for driver, count in sorted(duped_drivers.items(), key=lambda x: -x[1]):
                print(f"     • {driver}: {count} times")
        print()
    
    # Offer to fix
    print()
    print("=" * 70)
    response = input("Would you like to FIX these duplicates? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        fix_duplicates(client)
    else:
        print("No changes made. Exiting.")


def fix_duplicates(client: SheetsClient):
    """Fix duplicates by re-reading, deduplicating, and re-writing."""
    print()
    print("🔧 Fixing duplicates...")
    print()
    
    # Read sessions (this will parse and deduplicate automatically)
    sessions = read_results(client)
    
    print(f"✅ Loaded {len(sessions)} unique sessions from sheet")
    
    # Count total results
    total_results = sum(len(s.results) for s in sessions)
    print(f"✅ Total driver results: {total_results}")
    print()
    
    # Check for duplicates in loaded sessions
    session_keys = [s.session_key for s in sessions]
    key_counts = Counter(session_keys)
    if any(c > 1 for c in key_counts.values()):
        print("⚠️  Warning: Still have duplicate session keys after loading!")
        for key, count in key_counts.items():
            if count > 1:
                print(f"   Session key {key}: {count} times")
        print()
        
        # Deduplicate by keeping the last occurrence (newest data)
        seen = {}
        for s in sessions:
            seen[s.session_key] = s
        sessions = list(seen.values())
        print(f"🔧 Deduplicated to {len(sessions)} sessions")
        print()
    
    # Re-write to sheets
    calculator = ScoringCalculator(DEFAULT_RULES)
    
    response = input(f"Write {len(sessions)} clean sessions back to sheet? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        write_results(client, sessions, calculator)
        print()
        print("✅ Sheet updated successfully!")
        print()
        print("🏁 Recommendation: Restart your server to reload clean data")
    else:
        print("No changes made.")


def main():
    """Main entry point."""
    try:
        analyze_duplicates()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
