"""
AgriTrial OS - sync from the local SQLite database to Supabase.

Offline-first: records are always saved locally first. When there is a
connection, run this to push everything with synced = 0 to the cloud table.
If there is no connection nothing is lost - the records simply stay pending.

Setup: copy .env.example to .env and fill in your Supabase URL and service key.
Run:   python sync_supabase.py

Uses only the Python standard library (urllib), so nothing extra to install.
Sending a record that already exists updates it (last write wins).
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from db import get_unsynced_records, mark_synced

TABLE = "trial_measurements"
CONFLICT_COLUMNS = "trial_code,site_name,plot_number,trait_name,assessment_date"
BATCH_SIZE = 200


def load_env_file(path=None):
    """Read KEY=VALUE lines from .env into the environment (existing values win)."""
    path = Path(path) if path else Path(__file__).parent / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_payload(rows):
    """Drop the local-only data_id before sending."""
    return [{k: v for k, v in row.items() if k != "data_id"} for row in rows]


def _post_batch(url, key, rows, timeout):
    endpoint = f"{url.rstrip('/')}/rest/v1/{TABLE}?on_conflict={CONFLICT_COLUMNS}"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(build_payload(rows)).encode("utf-8"),
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status


def sync_to_supabase(timeout=10):
    """Push unsynced records. Returns a dict with status, synced and pending counts.
    status: ok | up_to_date | offline | not_configured | error"""
    load_env_file()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return {"status": "not_configured", "synced": 0, "pending": None,
                "detail": "set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"}

    rows = get_unsynced_records()
    if not rows:
        return {"status": "up_to_date", "synced": 0, "pending": 0}

    synced = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        try:
            _post_batch(url, key, batch, timeout)
        except urllib.error.HTTPError as err:       # server answered with an error
            return {"status": "error", "synced": synced, "pending": len(rows) - synced,
                    "detail": f"HTTP {err.code}: {err.read().decode('utf-8', 'ignore')[:200]}"}
        except (urllib.error.URLError, TimeoutError, OSError):   # no connection
            return {"status": "offline", "synced": synced, "pending": len(rows) - synced}
        mark_synced([row["data_id"] for row in batch])
        synced += len(batch)

    return {"status": "ok", "synced": synced, "pending": 0}


if __name__ == "__main__":
    print(sync_to_supabase())
