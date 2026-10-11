"""
Loads the sample field sheet for trial TOM-BIO-2026-02 (14 plots) into the
database, running every row through the same validation as the capture form.

Values were transcribed from the screenshot of the field sheet - check them
against the original before relying on them.

Run:  python seed_sample_data.py          (adds to the existing database)
      python seed_sample_data.py --reset  (deletes the database first)
"""
import os
import sys

from db import create_tables, db_path, save_record

TRIAL_CODE = "TOM-BIO-2026-02"
SITE = "Greenfield Research Farm, Block 4"

# (plot, date as written dd/m, treatment, rep, height, yield, spad, disease, root mass, notes)
# None = blank / illegible on the sheet.
SAMPLE_ROWS = [
    (101, "15/6", "Control",   1, 45,   2.1,  38,   15, 120, "normal - good stand"),
    (102, "15/6", "Control",   2, 47,   1.9,  39,   12, 115, "slight wilt on E side"),
    (103, "16/6", "Control",   3, 44,   2.0,  37,   18, 118, None),
    (104, "15/6", "BioStim-A", 1, 52,   2.8,  45,   8,  145, "good colour"),
    (105, "15/6", "BioStim-A", 2, 50,   2.7,  44,   7,  140, None),
    (106, "16/6", "BioStim-A", 3, 53,   2.9,  46,   6,  150, "biggest fruits - re-check ht?"),
    (107, "15/6", "BioStim-B", 1, None, 3.0,  41,   5,  160, "leaf curl - maybe overwatered? (height written as ??)"),
    (108, "31/6", "BioStim-B", 2, 48,   2.6,  42,   9,  135, "date must be 30/6 - wrote wrong"),
    (109, "16/6", "BioStim-B", 3, None, 2.5,  43,   10, 132, "illegible - looked ~50 cm but pencil smudged"),
    (110, "15/6", "BioStim-C", 1, 60,   3.5,  50,   3,  175, "excellent vigour"),
    (111, "16/6", "BioStim-C", 2, 58,   -3.2, 48,   4,  168, "negative value - scale tare error? ignore"),
    (112, "15/6", "BioStim-C", 3, 62,   3.8,  None, 2,  180, "SPAD meter battery died - no reading"),
    (113, None,   "Control",   4, None, None, None, None, None, "plot flooded after irrigation - skipped"),
    (114, "15/6", "BioStim-A", 1, 51,   2.75, 44,   7,  142, "duplicate rep - collector wrote Rep 1 again"),
]


def to_iso(raw):
    """'15/6' -> '2026-06-15'. Not checked here, so 31/6 reaches the validator."""
    if raw is None:
        return None
    day, month = raw.split("/")
    return f"2026-{int(month):02d}-{int(day):02d}"


def build_record(row):
    plot, date_raw, treatment, rep, height, yield_kg, spad, disease, root, notes = row
    return {
        "trial_code": TRIAL_CODE,
        "plot_id": plot,
        "date": to_iso(date_raw),
        "site": SITE,
        "crop": "Tomato",
        "variety": "Rutgers",
        "treatment_group": treatment,
        "rep_number": rep,
        "height_cm": height,
        "yield_value": yield_kg,
        "chlorophyll_spad": spad,
        "disease_pct": disease,
        "root_mass_g": root,
        "field_notes": notes,
    }


def seed():
    """Save every sample row. Returns {"saved": [...], "rejected": [(plot, errors), ...]}."""
    create_tables()
    saved, rejected = [], []
    for row in SAMPLE_ROWS:
        result = save_record(build_record(row))
        if result["saved"]:
            saved.append(result["record_id"])
        else:
            rejected.append((row[0], result["errors"]))
    return {"saved": saved, "rejected": rejected}


if __name__ == "__main__":
    if "--reset" in sys.argv and os.path.exists(db_path()):
        os.remove(db_path())

    summary = seed()
    print(f"Saved {len(summary['saved'])} of {len(SAMPLE_ROWS)} plots.")
    if summary["rejected"]:
        print("\nRejected - these need a person to review:")
        for plot, errors in summary["rejected"]:
            print(f"  Plot {plot}: " + "; ".join(errors))
