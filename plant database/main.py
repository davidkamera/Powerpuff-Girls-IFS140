"""AgriTrial API.  Run:  python -m uvicorn main:app --reload   then open /docs

In /docs: use POST /login with your website email + password, copy the access_token,
click the Authorize button and paste it. Then try the other endpoints."""
from statistics import mean, stdev
from typing import Optional

import json

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import db


class PrettyJSON(JSONResponse):
    """Indented JSON, so responses are readable straight in the browser."""
    def render(self, content) -> bytes:
        return json.dumps(content, indent=2, ensure_ascii=False).encode("utf-8")


DESCRIPTION = """
Field trial results from the **AgriTrial** platform, grouped by site and treatment group.

**How to use**
1. Run **POST /login** with your website email and password.
2. Copy the `access_token` and press **Authorize**. It is remembered when you refresh.
3. Try the endpoints below. Use a trial code from your dashboard.
"""

TAGS = [
    {"name": "Account", "description": "Sign in to get an access token."},
    {"name": "Trials", "description": "Your trials and their results by site and treatment group."},
]

app = FastAPI(title="AgriTrial API", version="1.0", description=DESCRIPTION,
              openapi_tags=TAGS, default_response_class=PrettyJSON, docs_url=None)

#API endpoint#
try:
    import capture  # type: ignore[import-not-found]
except ModuleNotFoundError:
    capture = None

if capture is not None:
    app.include_router(capture.router)

#  look and feel 
DOCS_CSS = """
<style>
  body { background: #f6fbf7; }
  .swagger-ui, .swagger-ui .opblock .opblock-summary-description { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
  .swagger-ui .info .title { color: #0a7a35; }
  .swagger-ui .info { margin: 32px 0 16px; }
  .swagger-ui .btn.authorize { color: #0a7a35; border-color: #0a7a35; }
  .swagger-ui .btn.authorize svg { fill: #0a7a35; }
  .swagger-ui .btn.execute { background: #02e255; border-color: #000; color: #000; font-weight: 700; }
  .swagger-ui .opblock.opblock-get { background: #eafcf0; border-color: #02e255; }
  .swagger-ui .opblock.opblock-get .opblock-summary-method { background: #0a7a35; }
  .swagger-ui .opblock.opblock-post { background: #eef6ff; }
  .swagger-ui .opblock-tag { border-bottom: 2px solid #02e255; }
  .swagger-ui .scheme-container { background: transparent; box-shadow: none; }
</style>
"""


@app.get("/docs", include_in_schema=False)
def docs():
    page = get_swagger_ui_html(
        openapi_url=app.openapi_url, title="AgriTrial API",
        swagger_ui_parameters={"persistAuthorization": True, "docExpansion": "list",
                               "defaultModelsExpandDepth": -1, "displayRequestDuration": True,
                               "syntaxHighlight.theme": "obsidian"})
    html = page.body.decode().replace("</head>", DOCS_CSS + "</head>")
    return HTMLResponse(html)


LANDING = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>AgriTrial API</title>
<style>
  body { margin:0; min-height:100vh; display:grid; place-items:center; background:#02e255;
         font-family:system-ui,-apple-system,"Segoe UI",sans-serif; color:#04210f; }
  main { background:#fff; max-width:520px; margin:24px; padding:40px; border-radius:12px;
         border:2px solid #000; box-shadow:6px 6px 0 #000; }
  h1 { margin:0 0 8px; font-size:2rem; } p { line-height:1.5; }
  a.btn { display:inline-block; margin:8px 8px 0 0; padding:10px 18px; border:2px solid #000;
          border-radius:6px; text-decoration:none; font-weight:700; color:#000; background:#02e255; }
  a.btn.alt { background:#fff; }
  a.btn:hover, a.btn:focus-visible { background:#000; color:#02e255; }
</style></head><body><main>
<h1>AgriTrial API</h1>
<p>Field trial results by site and treatment group. Sign in, then explore the endpoints.</p>
<a class="btn" href="/docs">Open the API docs</a><a class="btn alt" href="/redoc">Read the reference</a>
</main></body></html>"""


@app.get("/", include_in_schema=False)
def landing():
    return HTMLResponse(LANDING)
bearer = HTTPBearer(description="Supabase access_token from POST /login")


def token(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    return creds.credentials


def supabase_call(fn, *args):
    """Run a db function and turn Supabase errors into proper HTTP errors."""
    try:
        return fn(*args)
    except db.SupabaseError as e:
        status = 401 if e.status in (400, 401, 403) else 502
        raise HTTPException(status, e.message)
    except Exception as e:                      # network problems etc.
        raise HTTPException(502, f"Could not reach Supabase: {e}")


def load(trial_code, tok, site, treatment_group, date):
    records = supabase_call(db.get_records, trial_code, tok)
    if records is None:
        raise HTTPException(404, f"Trial '{trial_code}' not found")
    return [r for r in records
            if (site is None or r["site"] == site)
            and (treatment_group is None or r["treatment_group"] == treatment_group)
            and (date is None or r["date"] == date)]


def stats(values):
    return {"n": len(values), "mean": round(mean(values), 2),
            "sd": round(stdev(values), 2) if len(values) > 1 else None,
            "min": min(values), "max": max(values)}


class Login(BaseModel):
    email: str
    password: str


@app.post("/login", tags=["Account"], summary="Sign in")
def login(body: Login):
    """Exchange your website email + password for an access_token."""
    auth = supabase_call(db.login, body.email, body.password)
    return {"access_token": auth["access_token"], "expires_in": auth["expires_in"]}


@app.get("/trials", tags=["Trials"], summary="List your trials")
def trials(tok: str = Depends(token)):
    """Your trials."""
    return supabase_call(db.list_trials, tok)


@app.get("/trials/{trial_code}/records", tags=["Trials"], summary="Plot records")
def records(trial_code: str, site: Optional[str] = None,
            treatment_group: Optional[str] = None,
            date: Optional[str] = Query(None, description="YYYY-MM-DD"),
            tok: str = Depends(token)):
    """Plot records (one per plot per date), filtered by site / treatment group / date."""
    return load(trial_code, tok, site, treatment_group, date)


@app.get("/trials/{trial_code}/results", tags=["Trials"], summary="Results by site and treatment group")
def results(trial_code: str, site: Optional[str] = None,
            treatment_group: Optional[str] = None,
            trait: Optional[str] = Query(None, description="e.g. yield_value"),
            date: Optional[str] = Query(None, description="YYYY-MM-DD; omit to use every visit"),
            tok: str = Depends(token)):
    """Mean, sd, min, max and n per site and treatment group, for every trait.
    Note: with several visits per plot, each visit counts as one observation - filter
    by date to compare a single assessment."""
    groups = {}
    for r in load(trial_code, tok, site, treatment_group, date):
        g = groups.setdefault((r["site"], r["treatment_group"]), {"plots": set(), "values": {}})
        g["plots"].add(r["plot_number"])
        for name, value in r["values"].items():
            if value is not None and (trait is None or name == trait):
                g["values"].setdefault(name, []).append(value)
    return {"trial_code": trial_code,
            "groups": [{"site": s, "treatment_group": t, "plots": len(g["plots"]),
                        "traits": {k: stats(v) for k, v in g["values"].items()}}
                       for (s, t), g in sorted(groups.items())]}