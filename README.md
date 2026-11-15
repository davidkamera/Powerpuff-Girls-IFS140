# AgriTrial OS
# Team 02

AgriTrial OS helps farmers and researchers record, store and analyse field-trial measurements.
It has three parts that work together:

- **A website** (`index.html`) where users sign up, log in, enter trial readings and view a dashboard
  with treatment means, 95% confidence intervals and p-values.
- **An offline-first Python backend** with a local SQLite database (`agritrial.db`) that validates
  every record against the trial's protocol before saving it.
- **A Supabase cloud database** that holds the website's accounts and data, and receives the local
  readings when you run `syncing2supabase.py`.

```
 Browser (index.html -> sign up -> log in -> Dashboard / Enter data)
                         |
                         v
              Supabase (login + cloud database)  <----  syncing2supabase.py
                                                              ^
        Python backend: protocols.py + validation.py + db.py -> agritrial.db (SQLite)
```

## Quick start

**You need:** Python 3 (developed and tested on 3.13), a web browser and an internet connection for the
cloud parts. Run every command from the project folder.

### 1. Install the Python packages

```bash
pip install -r requirements.txt
```

### 2. Create the local database and load the sample data

```bash
python seed_sample_data.py --reset
```

`--reset` starts from an empty database. Expected result: **tomato 10 of 14 plots saved, canola 6 of 6
saved.** The 4 rejected tomato plots are:

- Plot 108 - date 31/6 does not exist
- Plot 111 - negative yield (-3.2)
- Plot 113 - skipped plot: no date, Rep 4 (only 3 planned), no measurements
- Plot 114 - duplicate of Plot 104 (BioStim-A, Rep 1)

A blank reading (for example Plot 112's missing SPAD) is allowed: an instrument failure should not stop
the rest of the record being saved. If you run the seed script on a database that already holds other
test records, more plots can be rejected as conflicts - use `--reset` to get the numbers above.

### 3. Sync the local records to the cloud

```bash
python syncing2supabase.py
```

This uploads every unsynced reading from `agritrial.db` to the `trial_measurements` table in Supabase.
It needs a `.env` file next to the script holding your Supabase project URL and secret key
(`SUPABASE_URL` and the key variable read at the top of `syncing2supabase.py`). The real key is not
included in the submission for security reasons.

The result is a status dictionary, for example `{'status': 'ok', 'synced': 1, 'pending': 0}`:

| Status | Meaning |
|---|---|
| `ok` | Readings were uploaded |
| `up_to_date` | Nothing waiting to be synced |
| `offline` | The cloud could not be reached. Readings stay `pending` locally and nothing is lost - run it again when you are online |
| `not_configured` | The `.env` file or its values are missing |
| `error` | Something else went wrong; the message explains what |

Uploads go in batches of 200 with up to 3 retries, and re-running is safe: a reading is matched on
trial, site, plot, test and date, so it is updated rather than duplicated.

### 4. Open the website

Open `index.html` in your browser. If sign-in misbehaves when the page is opened as a file, serve the
folder instead (`python -m http.server 8000`) and go to `http://localhost:8000/index.html`.

## Using the website

1. **Sign up.** On the start page (`index.html`) choose *Sign up*, fill in the form on `signup.html`
   and submit.
2. **Log in.** After signing up you are sent back to the login page. Log in with your new account.
3. **Dashboard.** You land on the dashboard. The navigation bar at the top has **Dashboard**,
   **Enter data** and **Log out**, and you can move between the pages at any time.
4. **Enter data.** On the *Enter trial data* page:
   - choose the trial and the plot (the site, treatment and replicate are shown);
   - check the date and type the name of whoever collected the data;
   - fill in the tests you measured and leave the rest blank. Each test shows its allowed range;
   - press **Save and go to next plot**. A green message confirms how many readings were saved and the
     form moves to the next plot. A red message explains anything wrong, such as a value outside the
     allowed range, and nothing is saved until every value is valid.
5. **Read the dashboard.** Pick a trial, then a test tab. The chart shows each treatment's mean with its
   95% confidence interval and a dashed line for the Control mean. A green bar means the treatment is
   clearly better than Control; orange means not clearly better. The summary table gives the mean,
   confidence interval, change vs Control and p-value, and the lower charts show the mean by site and
   the readings collected per week. Refresh the page after entering new data. If a trial has no data
   yet, you can switch on clearly labelled demo data.
6. **Log out** with the button in the navigation bar.

## Files

| File | What it does |
|---|---|
| `index.html` | Start page and login |
| `signup.html`, `signup.js` | Create a new account |
| `dashboard.html` | Dashboard: means, confidence intervals, p-values, site and weekly charts |
| `data-entry.html` | Form for entering readings |
| `api.js` | Functions the website uses to read and write the cloud database |
| `style.css` | Shared styling |
| `schema.sql` | The seven local (SQLite) tables |
| `protocols.py` | Trial definitions as data (tomato, canola) and the standard tests with their allowed ranges |
| `validation.py` | Rules that decide whether a record is acceptable |
| `db.py` | Functions the backend calls; creates `agritrial.db` |
| `seed_sample_data.py` | Registers both trials and loads the sample data |
| `syncing2supabase.py` | Pushes unsynced local readings to Supabase |
| `supabase_schema.sql` | The cloud tables - run once in the Supabase SQL Editor if you use your own project |
| `nitrate_analysis.py` | Calculates group means and 95% confidence intervals and draws the chart |
| `test_record.py`, `test_record2.py` | Save a test reading through the backend |
| `requirements.txt` | Python packages to install |

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
- **Repeated readings** - the same plot can be measured every fortnight.
- **Validation from data** - allowed ranges and treatments come from the trial's own protocol.
- **Calculated values are not stored** - `oil_yield` and `k_na_ratio` (canola) are worked out
  when the data is read.

## Validation rules

Every record is checked before it is saved, and each rejection explains what to fix:

- the date must be a real calendar date (`YYYY-MM-DD`) and is required;
- the replicate number must be within the trial's planned replicates;
- a plot cannot be re-used with a different treatment or replicate, and a treatment + replicate
  cannot be repeated at the same site;
- values must be inside the test's allowed range (for example pH 0 to 14, disease 0 to 100%, yield
  not below 0);
- the site must be registered for the trial, and any measurement name must be a test of that trial,
  so typos are rejected instead of creating new entries;
- a plot with no measurements at all is rejected as a skipped plot.

The website's data-entry page applies the same allowed ranges in the browser before saving.

## Backend functions (`db.py`)

The capture form sends **one flat record**. Fields marked * are required.

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

| Function | Gets |
|---|---|
| `save_record(record)` | `{"saved": True/False, "record_id": ..., "readings": n, "errors": [...]}` - show the errors |
| `list_trials()`, `load_protocol(trial_code)` | the trial's treatments, sites and tests |
| `get_records(trial_code, site, crop, treatment_group)` | one flat record per plot per date |
| `get_values("yield_value", "BioStim-A", crop="Tomato")` | raw numbers - means and CIs are calculated, never stored |
| `sync_to_supabase()` | status dictionary (same as `syncing2supabase.py`) |

Notes: `plot_id` is now `plot_number` (the old name is still accepted when saving); `crop` and
`variety` come from the trial; `record_id` is built as `trial_code-plot-date`; `trial_week` is
calculated from the date rather than stored.

## Website data access (`api.js`)

`const api = createApi(supabaseClient);` gives the pages these calls. Each returns a promise with the
rows, and throws an error with a readable message if the database refuses the request.

| Group | Calls | Notes |
|---|---|---|
| `api.trials` | `list()`, `create(row)`, `remove(id)` | `list()` returns the newest trial first |
| `api.sites` | `listForTrial(trialId)`, `create(row)`, `remove(id)` | table `trial_sites` |
| `api.treatments` | `listForTrial(trialId)`, `create(row)`, `remove(id)` | |
| `api.traits` | `listForTrial(trialId)`, `create(row)`, `remove(id)` | tests with unit and allowed range |
| `api.plots` | `listForTrial(trialId)`, `create(row)`, `remove(id)` | includes site and treatment names |
| `api.readings` | `listForTrial(trialId)`, `create(row)`, `remove(id)` | table `assessment_data` |

## How the statistics are calculated

Each plot's readings for a test are averaged first, so *n* is the number of plots in a treatment.
The 95% confidence interval is mean +/- t(0.975, n-1) x standard error. The p-value is a Welch
t-test of each treatment against Control. The dashboard and `nitrate_analysis.py` use the same method,
and the results were checked against hand calculations.

## Tests

- `python seed_sample_data.py --reset` shows valid plots saved and invalid plots rejected.
- `python test_record2.py` saves one valid reading and prints the result.
- `python nitrate_analysis.py` prints the group means and confidence intervals and draws the chart.
- `python syncing2supabase.py` shows the offline and online behaviour (`offline` with the record
  pending, then `ok`).

The full test cases, results, bug log and known limitations are in the Testing and Debugging Report.

## Add a new trial

Copy `TOMATO_TRIAL` in `protocols.py`, change the code, crop, treatments, sites and tests, then call
`register_trial(definition)`. No change to `schema.sql` or any other file.

## Using your own Supabase project

The submitted version already points at the team's Supabase project. To use your own:

1. In the SQL Editor, paste `supabase_schema.sql` and Run.
2. Put your project URL and secret key in `.env`.
3. Replace the project URL and public key near the top of `data-entry.html` and `dashboard.html`.
4. Run `python syncing2supabase.py`.


## Known limits

- Trials are registered from `protocols.py`; a registration page would be the next step.
- Sync is last-write-wins. Conflict review by the farmer is an Advanced Challenge item.
- The website has accounts (sign up and log in) but no role-based access.
- Readings entered on the website go straight to the cloud database and are checked by the page's own
  range checks, not by the Python validation. Duplicate-replicate and calendar-date checks apply to
  records saved through the Python backend.
- Tests were run as scripts and checked by hand; there is no automated test suite.

