"""Force sync: re-fetch all sessions from API and write to sheets."""
import os
import sys
sys.path.insert(0, ".")

import requests

# Load ADMIN_PASSWORD from .env if present (matches the server's config)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

token = os.getenv("ADMIN_PASSWORD", "")
headers = {"X-Admin-Token": token} if token else {}

# Trigger force sync via the API
print("Triggering FORCE sync (re-fetches all from API)...")
print("This may take 2-3 minutes due to API rate limits...")
resp = requests.post(
    "http://localhost:8000/api/sync/force", headers=headers, timeout=600
)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.json()}")
