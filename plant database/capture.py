"""Capture + sync endpoints backed by the local SQLite database.

Plug into main.py with:
    import capture
    app.include_router(capture.router)
"""
import sqlite3
from datetime import date
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

import local_db
import sync

local_db.init()                       # create tables on startup (safe to repeat)
router = APIRouter()
bearer = HTTPBearer(description="Supabase access_token from POST /login (only needed for /sync)")


def get_con():
    """One SQLite connection per request, always closed afterwards."""
    con = local_db.connect()
    try:
        yield con
    finally:
        con.close()


def write(fn, con, *args, **kwargs):
    """Run a db write and turn database errors into proper HTTP errors."""
    try:
        return fn(con, *args, **kwargs)
    except local_db.ValidationError as e:
        raise HTTPException(422, str(e))
    except ValueError as e:                                   # bad date format
        raise HTTPException(422, f"Invalid date, use YYYY-MM-DD ({e})")
    except sqlite3.IntegrityError as e:                       # duplicate / missing parent
        raise HTTPException(409, f"Not saved: {e}")


# ---------- models ----------

class TrialIn(BaseModel):
    trial_code: str
    crop: str
    trial_name: Optional[str] = None
    variety: Optional[str] = None
    planned_reps: int = Field(3, ge=1)


class SiteIn(BaseModel):
    trial_id: int
    site_name: str
    environment: Optional[str] = None


class TreatmentIn(BaseModel):
    trial_id: int
    treatment_name: str
    formulation_details: Optional[str] = None
    protocol_md: Optional[str] = None


class PlotIn(BaseModel):
    site_id: int
    treatment_id: int
    plot_number: int = Field(..., ge=1)
    replicate_number: int = Field(..., ge=1)


class RecordIn(BaseModel):
    plot_id: int
    visit_date: date = Field(default_factory=date.today)
    trial_week: Optional[int] = None
    observer: Optional[str] = None
    notes: Optional[str] = None
    values: Dict[str, Optional[float]] = Field(
        ..., examples=[{"nitrate_mg_l": 12.4, "ph": 6.1, "height_cm": 18.5}])


# ---------- setup ----------

@router.post("/local/trials", tags=["Setup"], summary="Add a trial", status_code=201)
def add_trial(body: TrialIn, con=Depends(get_con)):
    new_id = write(local_db.add_trial, con, **body.model_dump())
    con.commit()
    return {"trial_id": new_id}


@router.post("/local/sites", tags=["Setup"], summary="Add a site", status_code=201)
def add_site(body: SiteIn, con=Depends(get_con)):
    new_id = write(local_db.add_site, con, **body.model_dump())
    con.commit()
    return {"site_id": new_id}


@router.post("/local/treatments", tags=["Setup"], summary="Add a treatment group", status_code=201)
def add_treatment(body: TreatmentIn, con=Depends(get_con)):
    new_id = write(local_db.add_treatment, con, **body.model_dump())
    con.commit()
    return {"treatment_id": new_id}


@router.post("/local/plots", tags=["Setup"], summary="Add a plot", status_code=201)
def add_plot(body: PlotIn, con=Depends(get_con)):
    new_id = write(local_db.add_plot, con, **body.model_dump())
    con.commit()
    return {"plot_id": new_id}


@router.get("/local/traits", tags=["Setup"], summary="Measurements the form should show")
def traits(con=Depends(get_con)):
    """Standard plant + environmental measurements, with units and allowed ranges."""
    return [dict(r) for r in con.execute("SELECT * FROM traits ORDER BY category DESC, trait_id")]


@router.get("/local/plots", tags=["Setup"], summary="Plots to pick from in the form")
def plots(trial_code: str = Query(...), con=Depends(get_con)):
    rows = con.execute(
        "SELECT p.plot_id, p.plot_number, p.replicate_number, s.site_name, tr.treatment_name"
        " FROM plots p JOIN sites s ON s.site_id=p.site_id"
        " JOIN treatments tr ON tr.treatment_id=p.treatment_id"
        " JOIN trials t ON t.trial_id=s.trial_id WHERE t.trial_code=? ORDER BY p.plot_number",
        (trial_code,)).fetchall()
    return [dict(r) for r in rows]


# ---------- capture ----------

@router.post("/records", tags=["Capture"], summary="Save a plot visit", status_code=201)
def save_record(body: RecordIn, con=Depends(get_con)):
    """Saves all metrics for one plot on one date. Saving the same plot + date again
    replaces it and queues it for sync. Out-of-range values are rejected (422)."""
    rid = write(local_db.save_record, con, body.plot_id, body.visit_date.isoformat(),
                body.values, trial_week=body.trial_week, observer=body.observer, notes=body.notes)
    return {"record_id": rid, **local_db.sync_status(con)}


@router.get("/records", tags=["Capture"], summary="Locally stored records")
def list_records(trial_code: Optional[str] = None, pending_only: bool = False,
                 con=Depends(get_con)):
    return local_db.pending_records(con) if pending_only else local_db.all_records(con, trial_code)


# ---------- sync ----------

@router.get("/sync/status", tags=["Sync"], summary="How many records are waiting")
def sync_status(con=Depends(get_con)):
    return local_db.sync_status(con)


@router.post("/sync", tags=["Sync"], summary="Push waiting records to Supabase")
def run_sync(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    """Safe to call offline: records stay queued and the error is reported."""
    result = sync.push(creds.credentials)
    if result["error"] and result["pushed"] == 0 and result["pending"]:
        raise HTTPException(502, result["error"])
    return result