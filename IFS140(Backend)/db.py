
import os
import sqlite3
from pathlib import Path

from protocols import DERIVED_TRAITS
from validation import clean_record, measurements_in, validate_record

HERE = Path(__file__).parent
SCHEMA_PATH = HERE / "schema.sql"


def db_path():
    
    return os.environ.get("AGRITRIAL_DB", str(HERE / "agritrial.db"))


def get_connection():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables():
    conn = get_connection()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()



def register_trial(definition):
   
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT OR IGNORE INTO trials
           (trial_code, trial_name, crop, variety, objective, planned_reps, start_date, end_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (definition["trial_code"], definition.get("trial_name"), definition["crop"],
         definition.get("variety"), definition.get("objective"),
         definition.get("planned_reps", 3), definition.get("start_date"),
         definition.get("end_date")))
    cursor.execute("SELECT trial_id FROM trials WHERE trial_code = ?", (definition["trial_code"],))
    trial_id = cursor.fetchone()[0]

    for name, details in definition["treatments"].items():
        cursor.execute("""INSERT OR IGNORE INTO treatments (trial_id, treatment_name, formulation_details)
                          VALUES (?, ?, ?)""", (trial_id, name, details))
    for site_name, environment in definition.get("sites", []):
        cursor.execute("""INSERT OR IGNORE INTO trial_sites (trial_id, site_name, environment)
                          VALUES (?, ?, ?)""", (trial_id, site_name, environment))
    for name, label, category, unit, minimum, maximum, method in definition["traits"]:
        cursor.execute("""INSERT OR IGNORE INTO assessment_traits
                          (trial_id, trait_name, label, category, unit, min_value, max_value, methodology)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                       (trial_id, name, label, category, unit, minimum, maximum, method))
    conn.commit()
    conn.close()
    return trial_id


def list_trials():
    conn = get_connection()
    rows = conn.execute("SELECT trial_code, trial_name, crop, variety, planned_reps, status "
                        "FROM trials ORDER BY trial_id").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def load_protocol(trial_code):
    
    if not trial_code:
        return None
    conn = get_connection()
    trial = conn.execute("SELECT * FROM trials WHERE trial_code = ?", (trial_code,)).fetchone()
    if trial is None:
        conn.close()
        return None
    treatments = conn.execute("SELECT treatment_id, treatment_name FROM treatments WHERE trial_id = ?",
                              (trial["trial_id"],)).fetchall()
    sites = conn.execute("SELECT trial_site_id, site_name FROM trial_sites WHERE trial_id = ?",
                         (trial["trial_id"],)).fetchall()
    traits = conn.execute("SELECT trait_id, trait_name, unit, min_value, max_value "
                          "FROM assessment_traits WHERE trial_id = ?", (trial["trial_id"],)).fetchall()
    conn.close()
    return {
        "trial_id": trial["trial_id"],
        "crop": trial["crop"],
        "variety": trial["variety"],
        "planned_reps": trial["planned_reps"],
        "sites": {s["site_name"]: s["trial_site_id"] for s in sites},
        "treatments": {t["treatment_name"]: t["treatment_id"] for t in treatments},
        "traits": {t["trait_name"]: {"id": t["trait_id"], "unit": t["unit"],
                                     "min": t["min_value"], "max": t["max_value"]}
                   for t in traits},
    }



def _friendly_error(error):
    text = str(error)
    if "plots.trial_site_id, plots.treatment_id, plots.replicate_number" in text:
        return "duplicate replicate: this treatment and rep number already exist in this trial"
    if "assessment_data.plot_id" in text:
        return "a reading for this plot, test and date has already been captured"
    return text


def save_record(record):
    
    record = clean_record(record)
    protocol = load_protocol(record.get("trial_code"))
    errors = validate_record(record, protocol)
    record_id = f"{record.get('trial_code')}-{record.get('plot_number')}-{record.get('date')}"
    if errors:
        return {"saved": False, "record_id": record_id, "readings": 0, "errors": errors}

    readings = measurements_in(record, protocol)
    observer = record.get("observer") or record.get("collected_by")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        trial_site_id = protocol["sites"][record["site"]]
        treatment_id = protocol["treatments"][record["treatment_group"]]

        cursor.execute("SELECT plot_id, treatment_id, replicate_number FROM plots "
                       "WHERE trial_site_id = ? AND plot_number = ?",
                       (trial_site_id, record["plot_number"]))
        plot = cursor.fetchone()
        if plot is None:
            cursor.execute("INSERT INTO plots (trial_site_id, plot_number, treatment_id, replicate_number) "
                           "VALUES (?, ?, ?, ?)",
                           (trial_site_id, record["plot_number"], treatment_id, record["rep_number"]))
            plot_id = cursor.lastrowid
        elif plot["treatment_id"] != treatment_id or plot["replicate_number"] != record["rep_number"]:
            conn.rollback()
            return {"saved": False, "record_id": record_id, "readings": 0,
                    "errors": [f"plot {record['plot_number']} was already set up with a different "
                               "treatment or replicate number"]}
        else:
            plot_id = plot["plot_id"]

        for trait_name, value in readings.items():
            cursor.execute("INSERT INTO assessment_data "
                           "(plot_id, trait_id, assessment_date, numeric_value, collected_by) "
                           "VALUES (?, ?, ?, ?, ?)",
                           (plot_id, protocol["traits"][trait_name]["id"], record["date"], value, observer))
        if record.get("field_notes"):
            cursor.execute("INSERT INTO plot_notes (plot_id, note_date, note_text) VALUES (?, ?, ?) "
                           "ON CONFLICT(plot_id, note_date) DO UPDATE SET "
                           "note_text = note_text || ' | ' || excluded.note_text",
                           (plot_id, record["date"], record["field_notes"]))
        conn.commit()
    except sqlite3.IntegrityError as error:
        conn.rollback()
        return {"saved": False, "record_id": record_id, "readings": 0, "errors": [_friendly_error(error)]}
    finally:
        conn.close()

    return {"saved": True, "record_id": record_id, "readings": len(readings), "errors": []}



READING_SQL = """
    SELECT t.trial_code, t.crop, t.variety, ts.site_name, ts.environment,
           p.plot_number, tr.treatment_name, p.replicate_number,
           d.assessment_date, d.collected_by, d.synced,
           a.trait_name, d.numeric_value, n.note_text
    FROM assessment_data d
    JOIN plots p             ON d.plot_id = p.plot_id
    JOIN trial_sites ts      ON p.trial_site_id = ts.trial_site_id
    JOIN trials t            ON ts.trial_id = t.trial_id
    JOIN treatments tr       ON p.treatment_id = tr.treatment_id
    JOIN assessment_traits a ON d.trait_id = a.trait_id
    LEFT JOIN plot_notes n   ON n.plot_id = p.plot_id AND n.note_date = d.assessment_date
    WHERE 1=1
"""


def get_records(trial_code=None, site=None, crop=None, treatment_group=None):
    
    sql, params = READING_SQL, []
    for column, value in (("t.trial_code", trial_code), ("ts.site_name", site),
                          ("t.crop", crop), ("tr.treatment_name", treatment_group)):
        if value:
            sql += f" AND {column} = ?"
            params.append(value)
    sql += " ORDER BY p.plot_number, d.assessment_date, a.trait_id"

    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    records = {}
    for row in rows:
        key = (row["trial_code"], row["site_name"], row["plot_number"], row["assessment_date"])
        if key not in records:
            records[key] = {
                "record_id": f"{row['trial_code']}-{row['plot_number']}-{row['assessment_date']}",
                "trial_code": row["trial_code"], "crop": row["crop"], "variety": row["variety"],
                "site": row["site_name"], "environment": row["environment"],
                "plot_number": row["plot_number"], "treatment_group": row["treatment_name"],
                "rep_number": row["replicate_number"], "date": row["assessment_date"],
                "observer": row["collected_by"], "field_notes": row["note_text"], "synced": 1,
            }
        records[key][row["trait_name"]] = row["numeric_value"]
        if not row["synced"]:
            records[key]["synced"] = 0

    result = list(records.values())
    for record in result:
        for name, formula in DERIVED_TRAITS.get(record["trial_code"], {}).items():
            record[name] = formula(record)
    return result


def known_measures():
    
    conn = get_connection()
    names = {row[0] for row in conn.execute("SELECT DISTINCT trait_name FROM assessment_traits")}
    conn.close()
    for formulas in DERIVED_TRAITS.values():
        names.update(formulas)
    return names


def get_values(measure, treatment_group, site=None, crop=None, trial_code=None):
   
    if measure not in known_measures():
        raise ValueError(f"unknown measure '{measure}'")
    records = get_records(trial_code=trial_code, site=site, crop=crop,
                          treatment_group=treatment_group)
    return [r[measure] for r in records if r.get(measure) is not None]



def get_unsynced_records():
    
    sql = """
        SELECT d.data_id, t.trial_code, t.crop, t.variety, ts.site_name, p.plot_number,
               tr.treatment_name, p.replicate_number, a.trait_name, a.unit,
               d.assessment_date, d.numeric_value, d.collected_by, n.note_text AS field_notes
        FROM assessment_data d
        JOIN plots p             ON d.plot_id = p.plot_id
        JOIN trial_sites ts      ON p.trial_site_id = ts.trial_site_id
        JOIN trials t            ON ts.trial_id = t.trial_id
        JOIN treatments tr       ON p.treatment_id = tr.treatment_id
        JOIN assessment_traits a ON d.trait_id = a.trait_id
        LEFT JOIN plot_notes n   ON n.plot_id = p.plot_id AND n.note_date = d.assessment_date
        WHERE d.synced = 0
        ORDER BY d.data_id
    """
    conn = get_connection()
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def mark_synced(data_ids):
    conn = get_connection()
    conn.executemany("UPDATE assessment_data SET synced = 1 WHERE data_id = ?",
                     [(i,) for i in data_ids])
    conn.commit()
    conn.close()


if __name__ == "__main__":
    create_tables()
    print("Database ready at", db_path())
