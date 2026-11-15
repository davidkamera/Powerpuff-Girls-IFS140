# AgriTrial OS

Team 02, IFS140 Capstone 2026.

A low-cost, offline-first tool that lets small farmers and trial officers capture plant and environmental
readings on any device, check them as they are entered, and share them to the cloud when there is internet.
The data feeds confidence-interval charts and stakeholder reports for Group 3 biostimulant registration.

**Cost to run: R0.** Python and SQLite are free, and Supabase has a free tier.

## What is in this repository

| Folder | What it holds |
|---|---|
| `database/` | Local SQLite database, validation rules, sample data, Supabase sync and 27 automated tests |
| `backend/` | [CONFIRM: the API (FastAPI)] |
| `frontend/` | [CONFIRM: the capture form and dashboard] |
| `docs/` | [CONFIRM: the six Word documents, demo video and deck, or say where they are] |

## What you need

- Python 3.9 or newer (tested on 3.12)
- [CONFIRM: any packages for the API and dashboard, installed with `pip install -r requirements.txt`]

The database folder needs no extra packages.

## Quick start (works with no internet and no keys)

1. Load the sample data:
   ```
   cd database
   python seed_sample_data.py --reset
   ```
   Expected: `Tomato: saved 10 of 14 plots.` and `Canola: saved 6 of 6 plots.`, followed by four rejected
   tomato plots with the reason for each. Those four are deliberate: they show the validation working.

2. Run the tests:
   ```
   python -m unittest test_database -v
   ```
   Expected: 27 tests, then `OK`.

3. Start the API: [CONFIRM: exact command, for example `uvicorn main:app --reload` and the folder to run it from]

4. Open the web pages: [CONFIRM: file to open or address to visit]

## What to try (demo path)

1. Capture a valid record: it saves.
2. Capture a record with a negative yield: it is rejected with a clear message.
3. Sync to the cloud: the readings appear in Supabase.
4. Open the dashboard and compare Control with BioStim-A for yield.
   Expected: Control 2.00 ± 0.25 kg/plot and BioStim-A 2.80 ± 0.25 kg/plot (95% interval, 3 replicates each).
5. Open the second stakeholder view and download the DALRRD report.

## Optional: cloud sync with Supabase

The program works without this.

1. Create a free project at supabase.com.
2. In the SQL Editor, paste `database/supabase_schema.sql` and click Run.
3. Copy `database/.env.example` to `database/.env`. Fill in the project address (without `/rest/v1/`) and the secret key.
4. Run `python sync_supabase.py` from the `database` folder. Expected: status `ok`.

**Never commit `.env`.** It holds a secret key and is excluded by `.gitignore`.

## Documentation

- Technical Documentation: architecture, database, validation, API, security, set-up
- Testing Report, User Manual, Portfolio of Evidence, Group Reflection, Main Project Report
- [CONFIRM: say where they are in the repository]
