import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from db import get_unsynced_records, mark_synced

TABLE = "trial_measurements"
CONFLICT_COLUMNS = "trial_code,site_name,plot_number,trait_name,assessment_date"
BATCH_SIZE = 200
RETRIES = 3
BASE_DELAY = 2

def load_env_file(path=None):
    path = Path(path) if path else  Path(__file__).parent / ".env"
    if not path.exists():
           return

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or "=" not in line:
             continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))   

def build_payload(rows):
     return [{k:v for k, v in row.items() if k != "data_id"}for row in rows]

def _post_batch(url, key, rows, timeout):
    endpoint = (f"{url.rstrip('/')}/rest/v1/{TABLE}"
                f"?on_conflict={CONFLICT_COLUMNS}"
    )
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
 
 
def _send_with_retry(url, key, batch, timeout, retries, base_delay, sleep):
      for attempt in range(retries + 1):
        last_try = attempt == retries
        try:
            _post_batch(url, key, batch, timeout)
            return {"ok": True}
        except urllib.error.HTTPError as err:        
            temporary = err.code == 429 or err.code >= 500
            if not temporary or last_try:
                return {"ok": False, "status": "error",
                        "detail": f"HTTP {err.code}: {err.read().decode('utf-8', 'ignore')[:200]}"}
        except (urllib.error.URLError, TimeoutError, OSError): 
            if last_try:
                return {"ok": False, "status": "offline"}
        sleep(base_delay * (2 ** attempt))

def sync_to_supabase(timeout=10, retries=RETRIES, base_delay=BASE_DELAY, sleep=time.sleep):
    load_env_file()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return {"status": "not_configured", "synced": 0, "pending": None,
                "detail": "set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"}
    url = url.strip() .rstrip()
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    key = key.strip()
    if any(ch.isspace() for ch in url + key):
        return {
            "status": "not_configured",
            "synced": 0,
            "pending": None,
            "detail": "SUPABASE_URL or SUPABASE_SERVICE_KEY contains a space or line break",
        }

    rows = get_unsynced_records()
    if not rows:
        return {"status": "up_to_date", "synced": 0, "pending": 0}
 
    synced = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        result = _send_with_retry(url, key, batch, timeout, retries, base_delay, sleep)
        if not result["ok"]:
            outcome = {"status": result["status"], "synced": synced, "pending": len(rows) - synced}
            if "detail" in result:
                outcome["detail"] = result["detail"]
            return outcome
        mark_synced([row["data_id"] for row in batch]) 
        synced += len(batch)
 
    return {"status": "ok", "synced": synced, "pending": 0}
 
 
if __name__ == "__main__":
    print(sync_to_supabase()); 