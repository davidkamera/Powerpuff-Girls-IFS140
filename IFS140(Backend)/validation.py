"""
AgriTrial OS - validation rules (version 2).

The rules come from the trial's protocol (treatments, planned replicates, and the
allowed range of each test), so a new crop or a new test needs no code change.
Every rule here comes from a real problem on the sample field sheet: impossible
dates, negative yields, duplicate replicates, missing readings and blank plots.

protocol (built by db.load_protocol):
  {"trial_id", "crop", "variety", "planned_reps",
   "sites": {site_name: trial_site_id}, "treatments": {name: treatment_id},
   "traits": {trait_name: {"min": .., "max": .., "unit": ..}}}
"""
from datetime import datetime

REQUIRED_FIELDS = ["trial_code", "plot_number", "date", "site",
                   "treatment_group", "rep_number"]

# Fields that describe the plot/visit (everything else must be a test of the trial)
CONTEXT_KEYS = {"record_id", "trial_code", "plot_number", "plot_id", "date", "site",
                "environment", "crop", "variety", "treatment_group", "rep_number",
                "trial_week", "observer", "collected_by", "field_notes"}

TEXT_KEYS = {"record_id", "trial_code", "date", "site", "environment", "crop", "variety",
             "treatment_group", "observer", "collected_by", "field_notes"}

INTEGER_KEYS = {"plot_number", "plot_id", "rep_number", "trial_week"}


def _to_number(value, integer):
    """Turn '12' into 12 / 12.0. If it cannot be converted, return it unchanged
    so validate_record can report it."""
    if isinstance(value, bool):
        return value
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
    for key, value in record.items():
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                value = None
        if value is not None and key not in TEXT_KEYS:
            value = _to_number(value, key in INTEGER_KEYS)
        cleaned[key] = value
    # accept the old name for the field-sheet plot number
    if cleaned.get("plot_number") is None and cleaned.get("plot_id") is not None:
        cleaned["plot_number"] = cleaned["plot_id"]
    return cleaned


def measurements_in(record, protocol):
    """The {trait_name: value} pairs in a record (blank values are skipped)."""
    traits = protocol["traits"] if protocol else {}
    return {k: v for k, v in record.items()
            if k in traits and v is not None}


def validate_record(record, protocol):
    """Return a list of problems. An empty list means the record is valid."""
    errors = []

    for field in REQUIRED_FIELDS:
        if record.get(field) in (None, ""):
            errors.append(f"{field} is required")

    date_value = record.get("date")
    if date_value not in (None, ""):
        try:
            datetime.strptime(str(date_value), "%Y-%m-%d")
        except ValueError:
            errors.append(f"date '{date_value}' is not a real calendar date (use YYYY-MM-DD)")

    for field in INTEGER_KEYS:
        value = record.get(field)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            errors.append(f"{field} must be a whole number")

    trial_code = record.get("trial_code")
    if trial_code and protocol is None:
        errors.append(f"trial_code '{trial_code}' is not a registered trial")
        return errors          # nothing else can be checked without the protocol

    if protocol is None:
        return errors

    # Crop / variety must match the trial if the form sends them
    for field in ("crop", "variety"):
        given = record.get(field)
        if given and protocol[field] and given != protocol[field]:
            errors.append(f"{field} '{given}' does not match this trial ({protocol[field]})")

    site = record.get("site")
    if site and site not in protocol["sites"]:
        allowed = ", ".join(protocol["sites"])
        errors.append(f"site '{site}' is not registered for this trial (expected: {allowed})")

    treatment = record.get("treatment_group")
    if treatment and treatment not in protocol["treatments"]:
        allowed = ", ".join(protocol["treatments"])
        errors.append(f"treatment_group '{treatment}' is not in this trial (expected: {allowed})")

    rep = record.get("rep_number")
    if isinstance(rep, int) and not 1 <= rep <= protocol["planned_reps"]:
        errors.append(f"rep_number {rep} is outside the planned 1-{protocol['planned_reps']}")

    # Anything that is not plot/visit information must be a test of this trial
    for key in record:
        if key not in CONTEXT_KEYS and key not in protocol["traits"]:
            errors.append(f"'{key}' is not a test of this trial")

    # Measurements: numeric and inside the range stored for that test.
    # Blank is allowed (e.g. instrument failed); negative or text is not.
    measured = 0
    for name, value in measurements_in(record, protocol).items():
        limits = protocol["traits"][name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{name} '{value}' is not a number")
            continue
        measured += 1
        if limits["min"] is not None and value < limits["min"]:
            errors.append(f"{name} {value} is below the minimum of {limits['min']}")
        if limits["max"] is not None and value > limits["max"]:
            errors.append(f"{name} {value} is above the maximum of {limits['max']}")

    if measured == 0 and not errors_mention_numbers(errors):
        errors.append("no measurements recorded (blank or skipped plot)")

    fresh, dry = record.get("fresh_weight_g"), record.get("dry_weight_g")
    if isinstance(fresh, (int, float)) and isinstance(dry, (int, float)) and dry > fresh:
        errors.append("dry_weight_g cannot be more than fresh_weight_g")

    return errors


def errors_mention_numbers(errors):
    """True if a measurement was already reported as invalid (so 'no measurements'
    would be a misleading extra message)."""
    return any("is not a number" in e for e in errors)
