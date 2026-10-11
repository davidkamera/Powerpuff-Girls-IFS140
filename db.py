"""
AgriTrial OS - local database functions (SQLite, works offline).

Same pattern as the Week 19 practical: connect -> cursor -> execute with
? placeholders -> commit -> close.
"""
import os
import sqlite3
from pathlib import Path

from validation import clean_record, validate_record

HERE = Path(__file__).parent
SCHEMA_PATH = HERE / "schema.sql"

CONTEXT_COLUMNS = ["record_id", "trial_code", "plot_id", "date", "site", "environment",
                   "crop", "variety", "treatment_group", "rep_number", "trial_week",
                   "observer", "field_notes"]
PLANT_COLUMNS = ["height_cm", "leaf_count", "fresh_weight_g", "dry_weight_g",
                 "chlorophyll_spad", "root_mass_g", "yield_value", "disease_pct"]
ENV_COLUMNS = ["ph", "ec_mscm", "dissolved_o2", "temp_c", "humidity_pct",
               "nitrate_mgl", "phosphate_mgl"]

# measurement name -> table alias used in the JOIN below.
# Column names cannot be passed as ? placeholders, so only these are allowed.
MEASURES = {name: "pm" for name in PLANT_COLUMNS}
MEASURES.update({name: "er" for name in ENV_COLUMNS})

JOIN_SQL = """
    FROM trial_context tc
    JOIN plant_metrics pm ON tc.record_id = pm.record_id
    JOIN environmental_readings er ON tc.record_id = er.record_id
"""


def db_path():
    """Database file location (can be overridden with AGRITRIAL_DB)."""
    return os.environ.get("AGRITRIAL_DB", str(HERE / "agritrial.db"))


def get_connection():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables():
    """Create the three tables from schema.sql if they do not exist."""
    conn = get_connection()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def build_record_id(trial_code, plot_id):
    return f"{trial_code}-{plot_id}"


def _insert_sql(table, columns):
    marks = ", ".join("?" for _ in columns)
    return f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({marks})"


def _friendly_error(error):
    text = str(error)
    if "trial_context.record_id" in text:
        return "this plot has already been captured (record_id exists)"
    if "UNIQUE" in text:
        return "duplicate replicate: this treatment, rep number and date is already recorded"
    return text


def save_record(record):
    """Validate a record and save it to all three tables.
    Returns {"saved": True/False, "record_id": ..., "errors": [...]}."""
    record = clean_record(record)
    if not record.get("record_id") and record.get("trial_code") and record.get("plot_id") is not None:
        record["record_id"] = build_record_id(record["trial_code"], record["plot_id"])

    errors = validate_record(record)
    if errors:
        return {"saved": False, "record_id": record.get("record_id"), "errors": errors}

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(_insert_sql("trial_context", CONTEXT_COLUMNS),
                       tuple(record.get(c) for c in CONTEXT_COLUMNS))
        cursor.execute(_insert_sql("plant_metrics", ["record_id"] + PLANT_COLUMNS),
                       (record["record_id"],) + tuple(record.get(c) for c in PLANT_COLUMNS))
        cursor.execute(_insert_sql("environmental_readings", ["record_id"] + ENV_COLUMNS),
                       (record["record_id"],) + tuple(record.get(c) for c in ENV_COLUMNS))
        conn.commit()
    except sqlite3.IntegrityError as error:
        conn.rollback()
        return {"saved": False, "record_id": record["record_id"], "errors": [_friendly_error(error)]}
    finally:
        conn.close()

    return {"saved": True, "record_id": record["record_id"], "errors": []}


def _select_columns():
    parts = ["tc." + c for c in CONTEXT_COLUMNS + ["synced"]]
    parts += ["pm." + c for c in PLANT_COLUMNS]
    parts += ["er." + c for c in ENV_COLUMNS]
    return ", ".join(parts)


def get_records(trial_code=None, site=None, crop=None, treatment_group=None):
    """Return full records (all three tables joined), optionally filtered."""
    sql = "SELECT " + _select_columns() + JOIN_SQL + " WHERE 1=1"
    params = []
    for column, value in (("trial_code", trial_code), ("site", site),
                          ("crop", crop), ("treatment_group", treatment_group)):
        if value:
            sql += f" AND tc.{column} = ?"
            params.append(value)
    sql += " ORDER BY tc.plot_id"

    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_values(measure, treatment_group, site=None, crop=None, trial_code=None):
    """Raw values of one measurement for one treatment group.
    This is what the CI calculation uses - means and CIs are never stored."""
    if measure not in MEASURES:
        raise ValueError(f"unknown measure '{measure}'")
    alias = MEASURES[measure]
    sql = (f"SELECT {alias}.{measure} {JOIN_SQL} "
           f"WHERE tc.treatment_group = ? AND {alias}.{measure} IS NOT NULL")
    params = [treatment_group]
    for column, value in (("site", site), ("crop", crop), ("trial_code", trial_code)):
        if value:
            sql += f" AND tc.{column} = ?"
            params.append(value)

    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_unsynced_records():
    """Records that have not reached Supabase yet."""
    sql = "SELECT " + _select_columns() + JOIN_SQL + " WHERE tc.synced = 0 ORDER BY tc.plot_id"
    conn = get_connection()
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def mark_synced(record_ids):
    conn = get_connection()
    conn.executemany("UPDATE trial_context SET synced = 1 WHERE record_id = ?",
                     [(rid,) for rid in record_ids])
    conn.commit()
    conn.close()


if __name__ == "__main__":
    create_tables()
    print("Database ready at", db_path())
