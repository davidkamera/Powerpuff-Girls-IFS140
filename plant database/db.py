"""Reads your real data from Supabase through its REST API (PostgREST).

The logged-in user's token is passed along with every request, so Row Level Security
applies: a user only ever gets back their own trials.
"""
import os

import httpx

SUPABASE_URL = os.getenv("", "https://vfewattbwlfuxdcozouz.supabase.co")
# The anon key is public (it is already in your website's code). Never put the
# service_role key in this project.
SUPABASE_ANON_KEY = os.getenv(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZmZXdhdHRid2xmdXhkY296b3V6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE5MDk3MTYsImV4cCI6MjEwNzQ4NTcxNn0.vauaMzbxjwVi4VTA55TT6MtD7GM4hznt9ftIoyN3G2Q"
)

PAGE = 1000  # Supabase returns at most 1000 rows per request


class SupabaseError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def _headers(token=None):
    return {"apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {token or SUPABASE_ANON_KEY}"}


def _get(path, params, token):
    """One GET against /rest/v1/<path>. Returns the parsed JSON list."""
    r = httpx.get(f"{SUPABASE_URL}/rest/v1/{path}", params=params,
                  headers=_headers(token), timeout=20)
    if r.status_code != 200:
        try:
            message = r.json().get("message", r.text)
        except ValueError:
            message = r.text
        raise SupabaseError(r.status_code, message)
    return r.json()


def _get_all(path, params, token):
    """Keep fetching pages until every row has been read."""
    rows, offset = [], 0
    while True:
        page = _get(path, {**params, "limit": PAGE, "offset": offset}, token)
        rows += page
        if len(page) < PAGE:
            return rows
        offset += PAGE


def login(email, password):
    """Sign in with Supabase Auth and return the response (contains access_token)."""
    r = httpx.post(f"{SUPABASE_URL}/auth/v1/token", params={"grant_type": "password"},
                   headers={"apikey": SUPABASE_ANON_KEY},
                   json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        raise SupabaseError(r.status_code, r.json().get("msg") or r.json().get("error_description") or r.text)
    return r.json()


def list_trials(token):
    return _get_all("trials", {"select": "trial_code,trial_name,crop,variety,planned_reps,status",
                               "order": "trial_code"}, token)


def get_records(trial_code, token):
    """All readings of a trial, one record per plot per date:
    {trial_code, plot_number, date, site, treatment_group, rep_number, values: {trait: number}}
    Returns None if the trial does not exist (or is not visible to this user)."""
    trial = _get("trials", {"select": "trial_id", "trial_code": f"eq.{trial_code}"}, token)
    if not trial:
        return None
    trial_id = trial[0]["trial_id"]

    rows = _get_all("assessment_data", {
        "select": ("assessment_date,numeric_value,"
                   "assessment_traits!inner(trait_name,trial_id),"
                   "plots!inner(plot_id,plot_number,replicate_number,"
                   "trial_sites(site_name),treatments(treatment_name))"),
        "assessment_traits.trial_id": f"eq.{trial_id}",
        "order": "assessment_date,data_id",
    }, token)

    records = {}
    for row in rows:
        plot = row["plots"]
        key = (plot["plot_id"], row["assessment_date"])
        rec = records.setdefault(key, {
            "trial_code": trial_code,
            "plot_number": plot["plot_number"],
            "date": row["assessment_date"],
            "site": plot["trial_sites"]["site_name"],
            "treatment_group": plot["treatments"]["treatment_name"],
            "rep_number": plot["replicate_number"],
            "values": {},
        })
        rec["values"][row["assessment_traits"]["trait_name"]] = row["numeric_value"]
    return list(records.values())