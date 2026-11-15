from datetime import date

from db import create_tables, register_trial, save_record
from protocols import TOMATO_TRIAL


PLOT_NUMBER = 102                    
TREATMENT = "BioStim-A"              
REP_NUMBER = 1                       
OBSERVER = "Pablo"
READING_DATE = date.today().isoformat()   
FIELD_NOTES = None                   
ALL_TRAITS = False                  


create_tables()
register_trial(TOMATO_TRIAL)

traits = list(TOMATO_TRIAL["traits"])


def sample_value(minimum, maximum):
    """A believable value inside the allowed range."""
    if minimum is not None and maximum is not None:
        return round((minimum + maximum) / 2, 2)
    if minimum is not None:
        return minimum + 1
    if maximum is not None:
        return maximum - 1
    return 10.0


if ALL_TRAITS:
    chosen = traits
else:
    chosen = [next((t for t in traits if "nitrate" in t[0].lower()), traits[0])]

record = {
    "trial_code": TOMATO_TRIAL["trial_code"],
    "site": TOMATO_TRIAL["sites"][0][0],
    "plot_number": PLOT_NUMBER,
    "treatment_group": TREATMENT,
    "rep_number": REP_NUMBER,
    "date": READING_DATE,
    "observer": OBSERVER,
}
if FIELD_NOTES:
    record["field_notes"] = FIELD_NOTES

for name, label, category, unit, minimum, maximum in (t[:6] for t in chosen):
    record[name] = sample_value(minimum, maximum)
    print(f"Trait '{name}' ({unit}) = {record[name]}")

print(save_record(record))
