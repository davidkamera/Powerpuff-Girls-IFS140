"""
AgriTrial OS - validation rules.

Every rule here comes from a real problem in the sample field sheet
(trial TOM-BIO-2026-02): impossible dates, negative yields, duplicate
replicates, missing instrument readings and blank plots.
"""
from datetime import datetime

# Trial set-up (from the "Project Sample Data" slide).
# Later this can move into its own table so each trial carries its own protocol.
TRIALS = {
    "TOM-BIO-2026-02": {
        "site": "Greenfield Research Farm, Block 4",
        "crop": "Tomato",
        "variety": "Rutgers",
        "planned_reps": 3,
        "treatments": {
            "Control": "Untreated",
            "BioStim-A": "Seaweed extract",
            "BioStim-B": "Humic/fulvic acids",
            "BioStim-C": "Microbial consortium",
        },
    }
}

REQUIRED_FIELDS = ["trial_code", "plot_id", "date", "site", "crop",
                   "treatment_group", "rep_number"]

INTEGER_FIELDS = ["plot_id", "rep_number", "trial_week", "leaf_count"]

# field: (minimum, maximum)  - None means no limit
NUMERIC_RULES = {
    "height_cm": (0, 400),
    "leaf_count": (0, 1000),
    "fresh_weight_g": (0, None),
    "dry_weight_g": (0, None),
    "chlorophyll_spad": (0, 100),
    "root_mass_g": (0, None),
    "yield_value": (0, None),
    "disease_pct": (0, 100),
    "ph": (0, 14),
    "ec_mscm": (0, None),
    "dissolved_o2": (0, None),
    "temp_c": (-10, 60),
    "humidity_pct": (0, 100),
    "nitrate_mgl": (0, None),
    "phosphate_mgl": (0, None),
}


def _to_number(value, integer):
    """Turn '12' into 12 / 12.0. If it cannot be converted, return it unchanged
    so validate_record can report it."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return value
    if integer:
        return int(number) if number.is_integer() else value
    return number


def clean_record(record):
    """Trim text, turn empty strings into None and convert numeric strings."""
    cleaned = {}
    numeric_fields = set(NUMERIC_RULES) | set(INTEGER_FIELDS)
    for key, value in record.items():
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                value = None
        if value is not None and key in numeric_fields:
            value = _to_number(value, key in INTEGER_FIELDS)
        cleaned[key] = value
    return cleaned


def validate_record(record):
    """Return a list of problems. An empty list means the record is valid."""
    errors = []

    for field in REQUIRED_FIELDS:
        if record.get(field) in (None, ""):
            errors.append(f"{field} is required")

    # Real calendar date (catches 31/6)
    date_value = record.get("date")
    if date_value not in (None, ""):
        try:
            datetime.strptime(str(date_value), "%Y-%m-%d")
        except ValueError:
            errors.append(f"date '{date_value}' is not a real calendar date (use YYYY-MM-DD)")

    # Whole numbers
    for field in INTEGER_FIELDS:
        value = record.get(field)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            errors.append(f"{field} must be a whole number")

    # Trial protocol: known trial, known treatment, rep within the planned range
    trial_code = record.get("trial_code")
    trial = TRIALS.get(trial_code)
    if trial_code and trial is None:
        errors.append(f"trial_code '{trial_code}' is not a registered trial")
    if trial:
        treatment = record.get("treatment_group")
        if treatment and treatment not in trial["treatments"]:
            allowed = ", ".join(trial["treatments"])
            errors.append(f"treatment_group '{treatment}' is not in this trial (expected: {allowed})")
        rep = record.get("rep_number")
        if isinstance(rep, int) and not 1 <= rep <= trial["planned_reps"]:
            errors.append(f"rep_number {rep} is outside the planned 1-{trial['planned_reps']}")

    # Measurements: numeric and physically possible. Blank is allowed
    # (e.g. instrument failed), a negative or text value is not.
    measured = 0
    for field, (minimum, maximum) in NUMERIC_RULES.items():
        value = record.get(field)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{field} '{value}' is not a number")
            continue
        measured += 1
        if minimum is not None and value < minimum:
            errors.append(f"{field} {value} is below the minimum of {minimum}")
        if maximum is not None and value > maximum:
            errors.append(f"{field} {value} is above the maximum of {maximum}")

    if measured == 0:
        errors.append("no measurements recorded (blank or skipped plot)")

    # Cross-field check
    fresh, dry = record.get("fresh_weight_g"), record.get("dry_weight_g")
    if isinstance(fresh, (int, float)) and isinstance(dry, (int, float)) and dry > fresh:
        errors.append("dry_weight_g cannot be more than fresh_weight_g")

    return errors
