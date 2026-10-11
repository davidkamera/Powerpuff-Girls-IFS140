# AgriTrial OS - Database (version 2)

Local SQLite database that works offline, plus a one-table Supabase copy in the cloud.
Python standard library only - nothing to install, nothing to pay for.

## What changed from version 1, and why

Version 1 had one column per test (`height_cm`, `yield_value` ...). The lecturer's Week 20
slides call that design **not normalised** and **inflexible**: adding a test means changing the
table, a different crop carries columns it never uses, and each plot only holds one aggregated
reading even though measurements are taken at regular intervals.

Version 2 follows the lecturer's "Agri-Trial Schema 140" example:

| Table | Holds |
|---|---|
| `trials` | one row per trial: crop, variety, planned replicates |
| `treatments` | the treatments of a trial, with the protocol description (formulation) |
| `trial_sites` | where the trial runs |
| `plots` | one plot = one treatment + one replicate |
| `assessment_traits` | the tests this trial measures, with unit and allowed range |
| `assessment_data` | **one row per reading**: plot + test + date + value |
| `plot_notes` | handwritten field notes per plot and date |

What this gives the project:
- **Variable protocols** - a new trial, crop or test is new rows, not a new schema.
  `test_new_crop_needs_no_schema_change` adds a lettuce trial to prove it.
- **Repeated readings** - the same plot can be measured every fortnight.
- **Validation from data** - allowed ranges and treatments come from the trial's own protocol.
- **Calculated values are not stored** - `oil_yield` and `k_na_ratio` (canola) are worked out
  when the data is read.

## Files

| File | What it does |
|---|---|
| `schema.sql` | The seven local tables |
| `protocols.py` | Trial definitions as data (tomato, canola) and the standard tests |
| `validation.py` | Rules that decide whether a record is acceptable |
| `db.py` | Functions the back end calls |
| `seed_sample_data.py` | Registers both trials and loads the sample data |
| `supabase_schema.sql` | The cloud table - run once in the Supabase SQL Editor |
| `sync_supabase.py` | Pushes unsynced readings to Supabase |
| `test_database.py` | 27 automated tests |

## Run it

```bash
cd database_v2
python seed_sample_data.py --reset     # create the database and load the sample data
python -m unittest test_database -v    # run the tests
```

Expected: tomato 10 of 14 plots saved, canola 6 of 6 saved. The 4 rejected tomato plots are:

- Plot 108 - date 31/6 does not exist
- Plot 111 - negative yield (-3.2)
- Plot 113 - skipped plot: no date, Rep 4 (only 3 planned), no measurements
- Plot 114 - duplicate of Plot 104 (BioStim-A, Rep 1)

A blank reading (e.g. Plot 112's missing SPAD) is allowed: an instrument failure should not stop
the rest of the record being saved.

## What the other pages use

The capture form still sends **one flat record**. Fields marked * are required.

```json
{
  "trial_code": "TOM-BIO-2026-02",   *
  "plot_number": 104,                *
  "date": "2026-06-15",              *
  "site": "Greenfield Research Farm, Block 4",   *
  "treatment_group": "BioStim-A",    *
  "rep_number": 1,                   *
  "observer": "optional",
  "field_notes": "good colour",
  "height_cm": 52, "yield_value": 2.8, "chlorophyll_spad": 45,
  "disease_pct": 8, "root_mass_g": 145
}
```

| Page / person | Calls | Gets |
|---|---|---|
| Capture form (front end) | `save_record(record)` | `{"saved": True/False, "errors": [...]}` - show the errors |
| Form drop-downs | `list_trials()`, `load_protocol(trial_code)` | the trial's treatments, sites and tests |
| Records table / reports | `get_records(trial_code, site, crop, treatment_group)` | one flat record per plot per date |
| CI chart | `get_values("yield_value", "BioStim-A", crop="Tomato")` | raw numbers - means and CIs are calculated, never stored |
| Sync | `sync_to_supabase()` | status dictionary |

Changes your teammates need to know:
- `plot_id` is now `plot_number` (the old name is still accepted when saving).
- `crop` and `variety` come from the trial; send them only if you want them checked.
- `site` must be one registered for the trial - a typo is rejected instead of creating a new site.
- Any other field must be a test of that trial, so a misspelt test name is rejected.
- `record_id` is no longer stored; `get_records` builds one as `trial_code-plot-date`.
- `trial_week` is no longer stored - it can be calculated from the date.

## Add a new trial

Copy `TOMATO_TRIAL` in `protocols.py`, change the code, crop, treatments, sites and tests, then call
`register_trial(definition)`. No change to `schema.sql` or any other file.

## Connect to Supabase

1. In the SQL Editor, paste `supabase_schema.sql` and Run. This creates `trial_measurements`.
   The old `trial_data` table from version 1 can be deleted in the Table Editor.
2. Your `.env` file stays the same (`SUPABASE_URL` and the secret key).
3. `python sync_supabase.py` - expect `{'status': 'ok', 'synced': 173, 'pending': 0}` after seeding.

Statuses: `ok`, `up_to_date`, `offline` (readings stay pending), `not_configured`, `error`.
Not yet tested against a live project - the tests use a mocked connection.

## Things to confirm

- **Canola units** are not on the slide, so they are blank. The trial code `CANOLA-DEMO-01`, the
  site name and the date `2026-10-08` are placeholders.
- The slide calls one treatment "Fumic acid"; this uses "Fulvic acid" (slide 18 corrects the name).
- Values were typed in from screenshots - check them against the originals.

## Known limits (for the non-inclusion table)

- Trials are registered from `protocols.py`; a registration page would be the next step.
- Sync is last-write-wins. Conflict review by the farmer is an Advanced Challenge item.
- No user accounts or role-based access yet.
