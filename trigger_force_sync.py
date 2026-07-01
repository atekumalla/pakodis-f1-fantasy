"""Force sync: re-fetch all sessions from API and write to sheets."""
import sys
sys.path.insert(0, ".")

import requests

# Trigger force sync via the API
print("Triggering FORCE sync (re-fetches all from API)...")
print("This may take 2-3 minutes due to API rate limits...")
resp = requests.post("http://localhost:8000/api/sync/force", timeout=600)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.json()}")
