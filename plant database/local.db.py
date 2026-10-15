"""Local SQLite store for AgriTrial (offline-first capture).

Design:
  * Setup tables (trials, sites, treatments, plots) mirror the Supabase ones.
  * One capture = one `records` row (a plot on a date) + one `readings` row per metric.
  * Records use a client-generated UUID, so they can be created offline with no ID clash.
  * `synced_at IS NULL` means "not yet pushed to Supabase". Editing a record clears it.
  * Conflict rule: last write wins, decided by `updated_at` (see sync.py).
"""
from builtins import float
import json
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = "agritrial_local.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS trials (
    trial_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_code   TEXT NOT NULL UNIQUE,
    trial_name   TEXT,
    crop         TEXT NOT NULL,
    variety      TEXT,
    planned_reps INTEGER NOT NULL DEFAULT 3 CHECK (planned_reps >= 1)
);

CREATE TABLE IF NOT EXISTS sites (
    site_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id    INTEGER NOT NULL REFERENCES trials(trial_id) ON DELETE CASCADE,
    site_name   TEXT NOT NULL,
    environment TEXT,
    UNIQUE (trial_id, site_name)
);

CREATE TABLE IF NOT EXISTS treatments (
    treatment_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id            INTEGER NOT NULL REFERENCES trials(trial_id) ON DELETE CASCADE,
    treatment_name      TEXT NOT NULL,
    formulation_details TEXT,
    protocol_md         TEXT,              -- test protocol as Markdown (Challenge tier)
    UNIQUE (trial_id, treatment_name)
);

-- Standard measurements. min/max are enforced when saving a record.
CREATE TABLE IF NOT EXISTS traits (
    trait_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    trait_name TEXT NOT NULL UNIQUE,
    label      TEXT NOT NULL,
    unit       TEXT,
    category   TEXT NOT NULL CHECK (category IN ('plant', 'environment')),
    min_value  REAL,
    max_value  REAL
);

CREATE TABLE IF NOT EXISTS plots (
    plot_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id          INTEGER NOT NULL REFERENCES sites(site_id) ON DELETE CASCADE,
    treatment_id     INTEGER NOT NULL REFERENCES treatments(treatment_id) ON DELETE CASCADE,
    plot_number      INTEGER NOT NULL CHECK (plot_number >= 1),
    replicate_number INTEGER NOT NULL CHECK (replicate_number >= 1),
    UNIQUE (site_id, plot_number)
);

CREATE TABLE IF NOT EXISTS records (
    record_id  TEXT PRIMARY KEY,           -- UUID, created on the device
    plot_id    INTEGER NOT NULL REFERENCES plots(plot_id) ON DELETE CASCADE,
    visit_date TEXT NOT NULL,              -- YYYY-MM-DD
    trial_week INTEGER,
    observer   TEXT,
    notes      TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    synced_at  TEXT,                       -- NULL = waiting to sync
    UNIQUE (plot_id, visit_date)
);

CREATE TABLE IF NOT EXISTS readings (
    record_id     TEXT NOT NULL REFERENCES records(record_id) ON DELETE CASCADE,
    trait_id      INTEGER NOT NULL REFERENCES traits(trait_id),
    numeric_value REAL NOT NULL,
    PRIMARY KEY (record_id, trait_id)
);

CREATE INDEX IF NOT EXISTS idx_records_unsynced ON records(synced_at) WHERE synced_at IS NULL;
"""

# (trait_name, label, unit, category, min, max)
STANDARD_TRAITS = [
    ("height_cm",         "Plant height",       "cm",    "plant",        0, 300),
    ("leaf_count",        "Leaf count",         "",      "plant",        0, 500),
    ("fresh_weight_g",    "Fresh weight",       "g",     "plant",        0, 10000),
    ("dry_weight_g",      "Dry weight",         "g",     "plant",        0, 10000),
    ("spad",              "Chlorophyll (SPAD)", "SPAD",  "plant",        0, 100),
    ("root_length_cm",    "Root length",        "cm",    "plant",        0, 300),
    ("yield_value",       "Yield",              "g",     "plant",        0, 1000000),
    ("ph",                "pH",                 "",      "environment",  0, 14),
    ("ec_ms_cm",          "EC",                 "mS/cm", "environment",  0, 20),
    ("dissolved_o2_mg_l", "Dissolved O2",       "mg/L",  "environment",  0, 20),
    ("temp_c",            "Temperature",        "°C",    "environment", -10, 60),
    ("humidity_pct",      "Humidity",           "%",     "environment",  0, 100),
    ("nitrate_mg_l",      "Nitrate",            "mg/L",  "environment",  0, 2000),
    ("phosphate_mg_l",    "Phosphate",          "mg/L",  "environment",  0, 500),
]


class ValidationError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path=DB_PATH):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init(path=DB_PATH):
    """Create tables (safe to run repeatedly) and seed the standard traits."""
    with connect(path) as con:
        con.executescript(SCHEMA)
        con.executemany(
            "INSERT OR IGNORE INTO traits (trait_name,label,unit,category,min_value,max_value)"
            " VALUES (?,?,?,?,?,?)", STANDARD_TRAITS)


# ---------- setup helpers ----------

def _insert(con, sql, args):
    return con.execute(sql, args).lastrowid


def add_trial(con, trial_code, crop, trial_name=None, variety=None, planned_reps=3):
    return _insert(con, "INSERT INTO trials (trial_code,trial_name,crop,variety,planned_reps)"
                        " VALUES (?,?,?,?,?)", (trial_code, trial_name, crop, variety, planned_reps))


def add_site(con, trial_id, site_name, environment=None):
    return _insert(con, "INSERT INTO sites (trial_id,site_name,environment) VALUES (?,?,?)",
                   (trial_id, site_name, environment))


def add_treatment(con, trial_id, treatment_name, formulation_details=None, protocol_md=None):
    return _insert(con, "INSERT INTO treatments (trial_id,treatment_name,formulation_details,protocol_md)"
                        " VALUES (?,?,?,?)", (trial_id, treatment_name, formulation_details, protocol_md))


def add_plot(con, site_id, treatment_id, plot_number, replicate_number):
    return _insert(con, "INSERT INTO plots (site_id,treatment_id,plot_number,replicate_number)"
                        " VALUES (?,?,?,?)", (site_id, treatment_id, plot_number, replicate_number))


# ---------- capture ----------

def save_record(con, plot_id, visit_date, values, trial_week=None, observer=None, notes=None):
    """Save (or overwrite) every metric for one plot on one date.

    `values` is {trait_name: number}. Blank/None values are skipped. Nothing is written
    if any value is invalid. Returns the record_id.
    """
    traits = {t["trait_name"]: t for t in con.execute("SELECT * FROM traits")}
    clean, errors = {}, []
    for name, raw in values.items():
        if raw is None or raw == "":
            continue
        t = traits.get(name)
        if t is None:
            errors.append(f"Unknown measurement '{name}'")
            continue
        try:
            v = float(raw)
        except (TypeError, ValueError):
            errors.append(f"{t['label']}: '{raw}' is not a number")
            continue
        unit = f" {t['unit']}" if t["unit"] else ""
        if t["min_value"] is not None and v < t["min_value"]:
            errors.append(f"{t['label']} {v}{unit} is below the minimum of {t['min_value']}")
        elif t["max_value"] is not None and v > t["max_value"]:
            errors.append(f"{t['label']} {v}{unit} is above the maximum of {t['max_value']}")
        else:
            clean[t["trait_id"]] = v
    if errors:
        raise ValidationError("; ".join(errors))
    if not clean:
        raise ValidationError("Enter at least one measurement")
    datetime.strptime(visit_date, "%Y-%m-%d")  # raises ValueError on a bad date

    ts = now()
    existing = con.execute("SELECT record_id FROM records WHERE plot_id=? AND visit_date=?",
                           (plot_id, visit_date)).fetchone()
    if existing:
        rid = existing["record_id"]
        con.execute("UPDATE records SET trial_week=?, observer=?, notes=?, updated_at=?, synced_at=NULL"
                    " WHERE record_id=?", (trial_week, observer, notes, ts, rid))
        con.execute("DELETE FROM readings WHERE record_id=?", (rid,))
    else:
        rid = str(uuid.uuid4())
        con.execute("INSERT INTO records (record_id,plot_id,visit_date,trial_week,observer,notes,"
                    "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (rid, plot_id, visit_date, trial_week, observer, notes, ts, ts))
    con.executemany("INSERT INTO readings (record_id,trait_id,numeric_value) VALUES (?,?,?)",
                    [(rid, tid, v) for tid, v in clean.items()])
    con.commit()
    return rid


# ---------- reading back / sync support ----------

_RECORD_SQL = """
SELECT r.*, p.plot_number, p.replicate_number, s.site_name, s.environment,
       tr.treatment_name, t.trial_code, t.crop
FROM records r
JOIN plots p ON p.plot_id = r.plot_id
JOIN sites s ON s.site_id = p.site_id
JOIN treatments tr ON tr.treatment_id = p.treatment_id
JOIN trials t ON t.trial_id = s.trial_id
"""


def _export(con, row):
    vals = con.execute("SELECT t.trait_name, rd.numeric_value FROM readings rd"
                       " JOIN traits t ON t.trait_id = rd.trait_id WHERE rd.record_id=?",
                       (row["record_id"],)).fetchall()
    return {
        "record_id": row["record_id"], "trial_code": row["trial_code"], "crop": row["crop"],
        "site": row["site_name"], "environment": row["environment"],
        "treatment_group": row["treatment_name"], "plot_number": row["plot_number"],
        "rep_number": row["replicate_number"], "visit_date": row["visit_date"],
        "trial_week": row["trial_week"], "observer": row["observer"], "notes": row["notes"],
        "values": {v["trait_name"]: v["numeric_value"] for v in vals},
        "updated_at": row["updated_at"],
    }


def pending_records(con):
    """Denormalised records that still need to be pushed (the 'aggregated trial data')."""
    rows = con.execute(_RECORD_SQL + " WHERE r.synced_at IS NULL ORDER BY r.updated_at").fetchall()
    return [_export(con, r) for r in rows]


def all_records(con, trial_code=None):
    sql = _RECORD_SQL + (" WHERE t.trial_code=?" if trial_code else "") + " ORDER BY r.visit_date"
    rows = con.execute(sql, (trial_code,) if trial_code else ()).fetchall()
    return [_export(con, r) for r in rows]


def mark_synced(con, record_ids):
    con.executemany("UPDATE records SET synced_at=? WHERE record_id=?",
                    [(now(), rid) for rid in record_ids])
    con.commit()


def sync_status(con):
    r = con.execute("SELECT COUNT(*) total, SUM(synced_at IS NULL) pending FROM records").fetchone()
    return {"total": r["total"], "pending": r["pending"] or 0}