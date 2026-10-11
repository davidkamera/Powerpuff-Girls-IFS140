-- AgriTrial OS - local (offline) SQLite schema, version 2
-- Based on the lecturer's Week 20 "Agri-Trial Schema 140" example.
--
-- Why this shape: a "wide" table with one column per test is not normalised and is
-- inflexible (a new test means a new column; a different trial carries columns it never
-- uses). Here the master data is separate, and every reading is one row in
-- assessment_data: plot + trait + date + value. New tests, new crops and repeated
-- fortnightly readings need NO schema change.
-- Rule kept from v1: nothing that can be calculated (means, CIs, trial week) is stored.

-- A trial: one crop, one set of treatments, one set of tests
CREATE TABLE IF NOT EXISTS trials (
    trial_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_code    TEXT NOT NULL UNIQUE,        -- e.g. TOM-BIO-2026-02
    trial_name    TEXT,
    crop          TEXT NOT NULL,               -- e.g. Tomato, Canola
    variety       TEXT,                        -- e.g. Rutgers
    objective     TEXT,
    planned_reps  INTEGER NOT NULL DEFAULT 3,  -- replicates planned per treatment
    start_date    TEXT,
    end_date      TEXT,
    status        TEXT NOT NULL DEFAULT 'active'
);

-- Treatment groups of a trial, with the protocol description (formulation) stored as text
CREATE TABLE IF NOT EXISTS treatments (
    treatment_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id             INTEGER NOT NULL REFERENCES trials(trial_id) ON DELETE CASCADE,
    treatment_name       TEXT NOT NULL,        -- Control, BioStim-A ...
    formulation_details  TEXT,                 -- protocol description (Markdown allowed)
    UNIQUE (trial_id, treatment_name)
);

-- Where a trial is run (a trial can run at several sites)
CREATE TABLE IF NOT EXISTS trial_sites (
    trial_site_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id       INTEGER NOT NULL REFERENCES trials(trial_id) ON DELETE CASCADE,
    site_name      TEXT NOT NULL,
    environment    TEXT,
    UNIQUE (trial_id, site_name)
);

-- A physical plot. One plot = one treatment + one replicate.
CREATE TABLE IF NOT EXISTS plots (
    plot_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_site_id     INTEGER NOT NULL REFERENCES trial_sites(trial_site_id) ON DELETE CASCADE,
    plot_number       INTEGER NOT NULL,        -- number on the field sheet (101, 102 ...)
    treatment_id      INTEGER NOT NULL REFERENCES treatments(treatment_id),
    replicate_number  INTEGER NOT NULL,
    UNIQUE (trial_site_id, plot_number),
    -- the same replicate of a treatment cannot be set up twice ("collector wrote Rep 1 again")
    UNIQUE (trial_site_id, treatment_id, replicate_number)
);

-- The tests a trial measures. The allowed range lives here, so validation is data-driven.
CREATE TABLE IF NOT EXISTS assessment_traits (
    trait_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id     INTEGER NOT NULL REFERENCES trials(trial_id) ON DELETE CASCADE,
    trait_name   TEXT NOT NULL,                -- code used in forms and the API, e.g. yield_value
    label        TEXT,                         -- display name, e.g. "Yield"
    category     TEXT NOT NULL DEFAULT 'plant',  -- plant | environment | quality
    unit         TEXT,
    methodology  TEXT,
    min_value    REAL,                         -- NULL = no limit
    max_value    REAL,
    UNIQUE (trial_id, trait_name)
);

-- One row per reading: plot + trait + date + value (the "vertical" table)
CREATE TABLE IF NOT EXISTS assessment_data (
    data_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    plot_id          INTEGER NOT NULL REFERENCES plots(plot_id) ON DELETE CASCADE,
    trait_id         INTEGER NOT NULL REFERENCES assessment_traits(trait_id),
    assessment_date  TEXT NOT NULL,            -- ISO format YYYY-MM-DD
    numeric_value    REAL NOT NULL,
    collected_by     TEXT,
    synced           INTEGER NOT NULL DEFAULT 0,   -- 0 = not yet in Supabase, 1 = synced
    -- the same reading cannot be captured twice, but a plot can be measured again on a later date
    UNIQUE (plot_id, trait_id, assessment_date)
);

-- Handwritten field notes for a plot on a visit ("slight wilt on E side")
CREATE TABLE IF NOT EXISTS plot_notes (
    note_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    plot_id    INTEGER NOT NULL REFERENCES plots(plot_id) ON DELETE CASCADE,
    note_date  TEXT NOT NULL,
    note_text  TEXT NOT NULL,
    UNIQUE (plot_id, note_date)
);
