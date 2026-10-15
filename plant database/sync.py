"""Push unsynced local records to ONE Supabase table (`trial_records`).

Safe to run when offline: it fails quietly and the records stay queued.
Conflict rule: last write wins. The upsert is keyed on record_id, and the database trigger
in trial_records.sql ignores an incoming row whose updated_at is older than the stored one.

Usage:
    python sync.py you@email.com yourpassword
"""
import sys

import httpx  # pyright: ignore[reportMissingImports]

import db            # reuses your login() and Supabase settings
import local_db # pyright: ignore[reportMissingImports]

BATCH = 200


def push(token, path=local_db.DB_PATH):
    """Returns {'pushed': n, 'pending': n, 'error': str|None}."""
    con = local_db.connect(path)
    pending = local_db.pending_records(con)
    pushed = 0
    try:
        for i in range(0, len(pending), BATCH):
            chunk = pending[i:i + BATCH]
            r = httpx.post(
                f"{db.SUPABASE_URL}/rest/v1/trial_records",
                params={"on_conflict": "record_id"},
                headers={**db._headers(token), "Content-Type": "application/json",
                         "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=chunk, timeout=30)
            if r.status_code not in (200, 201, 204):
                return {"pushed": pushed, "pending": len(pending) - pushed,
                        "error": f"Supabase {r.status_code}: {r.text}"}
            local_db.mark_synced(con, [c["record_id"] for c in chunk])
            pushed += len(chunk)
    except httpx.HTTPError as e:      # offline / timeout: keep the queue, try again later
        return {"pushed": pushed, "pending": len(pending) - pushed, "error": f"Offline? {e}"}
    finally:
        con.close()
    return {"pushed": pushed, "pending": 0, "error": None}


if __name__ == "__main__":
    local_db.init()
    auth = db.login(sys.argv[1], sys.argv[2])
    print(push(auth["access_token"]))