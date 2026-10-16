"""
One-off test: save one reading locally, so syncing2supabase.py has something to send.
Run from the IFS140 folder:  python test_record.py
Picks a real trait from STANDARD_TRAITS (prefers nitrate) and a value inside its range.
"""
from db import create_tables, register_trial, save_record
from protocols import TOMATO_TRIAL

create_tables()
register_trial(TOMATO_TRIAL)

# each trait is (name, label, category, unit, minimum, maximum, method) - same order db.py uses
traits = list(TOMATO_TRIAL["traits"])
chosen = next((t for t in traits if "nitrate" in t[0].lower()), traits[0])
name, label, category, unit, minimum, maximum = chosen[:6]

if minimum is not None and maximum is not None:
    value = round((minimum + maximum) / 2, 2)
elif minimum is not None:
    value = minimum + 1
elif maximum is not None:
    value = maximum - 1
else:
    value = 10.0

print(f"Testing trait '{name}' ({unit}) with value {value}")

record = {
    "trial_code": TOMATO_TRIAL["trial_code"],
    "site": TOMATO_TRIAL["sites"][0][0],
    "plot_number": 101,
    "treatment_group": "Control",
    "rep_number": 1,
    "date": "2026-10-12",
    "observer": "Pablo",
    name: value,
}
print(save_record(record))
