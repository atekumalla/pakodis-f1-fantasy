#!/usr/bin/env python3
"""
Emergency sheet cleaner - DIRECTLY removes duplicate rows from Google Sheets
"""
from collections import defaultdict
from src.sheets.client import SheetsClient

def main():
    print("🚨 Emergency cleanup starting...")
    
    client = SheetsClient()
    
    # Read raw data
    print("📖 Reading raw sheet data...")
    data = client.read_all_values('Session Results')
    
    if not data or len(data) < 2:
        print("❌ No data found")
        return
    
    headers = data[0]
    rows = data[1:]
    
    print(f"📊 Current: {len(rows)} rows")
    
    # Deduplicate: keep first occurrence of each (date, round, grand_prix, session, driver)
    seen = set()
    unique_rows = []
    duplicates_removed = 0
    
    for row in rows:
        if not row or len(row) < 6:
            continue
        
        # Key: (date, round, grand_prix, session, driver_name, driver_number)
        key = tuple(row[0:6])  # Date, Round, Grand Prix, Session, Half, Driver
        
        if key not in seen:
            seen.add(key)
            unique_rows.append(row)
        else:
            duplicates_removed += 1
    
    print(f"✅ Removed {duplicates_removed} duplicate rows")
    print(f"📊 New count: {len(unique_rows)} unique rows")
    
    # Write back
    print("🔧 Writing clean data back to sheet...")
    all_data = [headers] + unique_rows
    client.write_all_values('Session Results', all_data)
    
    print("✅ DONE! Sheet cleaned successfully")
    
    # Verify
    print("\n🔍 Verifying...")
    verify_data = client.read_all_values('Session Results')
    print(f"✅ Sheet now has {len(verify_data)-1} rows")

if __name__ == "__main__":
    main()
