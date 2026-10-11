-- AgriTrial OS - local (offline) SQLite schema
-- Field names match the sample trial TOM-BIO-2026-02 and the Member 6 document.
-- Rule: nothing that can be calculated (means, CIs) is stored here.

CREATE TABLE IF NOT EXISTS trial_context (
    record_id        TEXT PRIMARY KEY,      -- trial_code + plot_id, e.g. TOM-BIO-2026-02-104
    trial_code       TEXT NOT NULL,         -- e.g. TOM-BIO-2026-02
    plot_id          INTEGER NOT NULL,      -- plot number on the field sheet (101-114)
    date             TEXT NOT NULL,         -- ISO format YYYY-MM-DD
    site             TEXT NOT NULL,         -- e.g. Greenfield Research Farm, Block 4
    environment      TEXT,
    crop             TEXT NOT NULL,         -- e.g. Tomato
    variety          TEXT,                  -- e.g. Rutgers
    treatment_group  TEXT NOT NULL,         -- Control, BioStim-A, BioStim-B, BioStim-C
    rep_number       INTEGER NOT NULL,      -- replicate number (3 planned per treatment)
    trial_week       INTEGER,
    observer         TEXT,
    field_notes      TEXT,                  -- handwritten notes from the field sheet
    synced           INTEGER NOT NULL DEFAULT 0,   -- 0 = not yet in Supabase, 1 = synced
    -- stops the same replicate being captured twice (e.g. "collector wrote Rep 1 again")
    UNIQUE (trial_code, treatment_group, rep_number, date)
);

CREATE TABLE IF NOT EXISTS plant_metrics (
    record_id         TEXT PRIMARY KEY REFERENCES trial_context(record_id) ON DELETE CASCADE,
    height_cm         REAL,
    leaf_count        INTEGER,
    fresh_weight_g    REAL,
    dry_weight_g      REAL,
    chlorophyll_spad  REAL,
    root_mass_g       REAL,
    yield_value       REAL,                 -- kg/plot
    disease_pct       REAL
);

CREATE TABLE IF NOT EXISTS environmental_readings (
    record_id      TEXT PRIMARY KEY REFERENCES trial_context(record_id) ON DELETE CASCADE,
    ph             REAL,
    ec_mscm        REAL,
    dissolved_o2   REAL,
    temp_c         REAL,
    humidity_pct   REAL,
    nitrate_mgl    REAL,
    phosphate_mgl  REAL
);
