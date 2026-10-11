"""
Registers two trials and loads their sample data through the same validation as the
capture form:

  1. Tomato  TOM-BIO-2026-02  - the 14-plot field sheet (messy handwritten data)
  2. Canola  CANOLA-DEMO-01   - the 6-row table from the Week 20 slides

Two different crops with different tests, one schema, no changes - that is the point.
Values were typed in from screenshots: check them against the originals.

Run:  python seed_sample_data.py          (adds to the existing database)
      python seed_sample_data.py --reset  (deletes the database first)
"""
import os
import sys

from db import create_tables, db_path, register_trial, save_record
from protocols import CANOLA_TRIAL, TOMATO_TRIAL

# ------------------------------------------------------------------ tomato field sheet
# (plot, date as written dd/m, treatment, rep, height, yield, spad, disease, root mass, notes)
# None = blank / illegible on the sheet.
TOMATO_ROWS = [
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

# ------------------------------------------------------------------ canola table (slide 4)
# Oil.yield and K/Na are left out on purpose: they are calculated, not stored.
CANOLA_TRAIT_ORDER = ["yield_value", "bio_yield", "pods_per_plant", "seeds_per_pod",
                      "thousand_seed_weight", "oil_pct", "n", "p", "k", "na", "ca", "mg",
                      "fe", "mn", "zn", "cu", "chl_a", "chl_b", "rwc", "ionic_l", "prolin"]
CANOLA_ROWS = [
    ("Control",         [2286, 9545,  82.6,  25.3, 3.96, 33.2, 2.11, 0.49, 3.8, 0.97, 3.35, 0.61, 116, 63.2, 32.4, 6.84, 1.59, 0.51, 69.2, 23.7, 2.19]),
    ("Amino acid",      [2718, 11512, 102.6, 31.3, 4.06, 29.4, 2.35, 0.61, 4.2, 0.72, 3.81, 0.56, 135, 70.2, 30.6, 7.91, 1.72, 0.66, 71.2, 22.5, 1.91]),
    ("Seaweed Extract", [2738, 12929, 111.2, 27.3, 4.95, 32.6, 2.71, 0.68, 4.1, 0.69, 4.21, 0.64, 178, 80.3, 35.3, 9.99, 1.66, 0.61, 65.6, 20.2, 2.09]),
    ("Humic acid",      [2589, 9856,  98.6,  27.3, 3.69, 35.6, 2.15, 0.56, 4.0, 0.76, 3.58, 0.55, 189, 79.6, 37.8, 8.86, 1.75, 0.55, 69.3, 19.7, 1.98]),
    ("Fulvic acid",     [2599, 14126, 116.2, 34.3, 4.86, 33.6, 2.39, 0.62, 4.5, 0.71, 4.01, 0.65, 176, 89.3, 38.7, 7.81, 1.73, 0.66, 71.5, 21.6, 1.99]),
    ("Combined",        [3196, 14093, 120.4, 32.1, 5.89, 29.3, 2.33, 0.72, 4.1, 0.59, 4.21, 0.67, 191, 92.1, 39.2, 8.15, 1.73, 0.72, 72.1, 16.9, 2.06]),
]
CANOLA_DATE = "2026-10-08"      # placeholder: the slide gives no date (slide 17 uses this default)


def to_iso(raw):
    """'15/6' -> '2026-06-15'. Not checked here, so 31/6 reaches the validator."""
    if raw is None:
        return None
    day, month = raw.split("/")
    return f"2026-{int(month):02d}-{int(day):02d}"


def tomato_record(row):
    plot, date_raw, treatment, rep, height, yield_kg, spad, disease, root, notes = row
    return {
        "trial_code": TOMATO_TRIAL["trial_code"], "plot_number": plot, "date": to_iso(date_raw),
        "site": TOMATO_TRIAL["sites"][0][0], "treatment_group": treatment, "rep_number": rep,
        "height_cm": height, "yield_value": yield_kg, "chlorophyll_spad": spad,
        "disease_pct": disease, "root_mass_g": root, "field_notes": notes,
    }


def canola_record(plot_number, treatment, values):
    record = {
        "trial_code": CANOLA_TRIAL["trial_code"], "plot_number": plot_number, "date": CANOLA_DATE,
        "site": CANOLA_TRIAL["sites"][0][0], "treatment_group": treatment, "rep_number": 1,
    }
    record.update(dict(zip(CANOLA_TRAIT_ORDER, values)))
    return record


def _load(records):
    saved, rejected = [], []
    for plot_number, record in records:
        result = save_record(record)
        if result["saved"]:
            saved.append(plot_number)
        else:
            rejected.append((plot_number, result["errors"]))
    return {"saved": saved, "rejected": rejected}


def seed():
    """Register both trials and load their data.
    Returns {"tomato": {"saved": [...], "rejected": [...]}, "canola": {...}}."""
    create_tables()
    register_trial(TOMATO_TRIAL)
    register_trial(CANOLA_TRIAL)
    tomato = _load([(row[0], tomato_record(row)) for row in TOMATO_ROWS])
    canola = _load([(number, canola_record(number, treatment, values))
                    for number, (treatment, values) in enumerate(CANOLA_ROWS, start=1)])
    return {"tomato": tomato, "canola": canola}


if __name__ == "__main__":
    if "--reset" in sys.argv and os.path.exists(db_path()):
        os.remove(db_path())

    summary = seed()
    print(f"Tomato: saved {len(summary['tomato']['saved'])} of {len(TOMATO_ROWS)} plots.")
    print(f"Canola: saved {len(summary['canola']['saved'])} of {len(CANOLA_ROWS)} plots.")
    if summary["tomato"]["rejected"] or summary["canola"]["rejected"]:
        print("\nRejected - these need a person to review:")
        for crop in ("tomato", "canola"):
            for plot, errors in summary[crop]["rejected"]:
                print(f"  {crop.title()} plot {plot}: " + "; ".join(errors))
