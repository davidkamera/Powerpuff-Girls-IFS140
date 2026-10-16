
CREATE TABLE IF NOT EXISTS trials (
    trial_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_code    TEXT NOT NULL UNIQUE,        
    trial_name    TEXT,
    crop          TEXT NOT NULL,               
    variety       TEXT,                        
    objective     TEXT,
    planned_reps  INTEGER NOT NULL DEFAULT 3, 
    start_date    TEXT,
    end_date      TEXT,
    status        TEXT NOT NULL DEFAULT 'active'
);


CREATE TABLE IF NOT EXISTS treatments (
    treatment_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id             INTEGER NOT NULL REFERENCES trials(trial_id) ON DELETE CASCADE,
    treatment_name       TEXT NOT NULL,        
    formulation_details  TEXT,                 
    UNIQUE (trial_id, treatment_name)
);


CREATE TABLE IF NOT EXISTS trial_sites (
    trial_site_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id       INTEGER NOT NULL REFERENCES trials(trial_id) ON DELETE CASCADE,
    site_name      TEXT NOT NULL,
    environment    TEXT,
    UNIQUE (trial_id, site_name)
);


CREATE TABLE IF NOT EXISTS plots (
    plot_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_site_id     INTEGER NOT NULL REFERENCES trial_sites(trial_site_id) ON DELETE CASCADE,
    plot_number       INTEGER NOT NULL,        
    treatment_id      INTEGER NOT NULL REFERENCES treatments(treatment_id),
    replicate_number  INTEGER NOT NULL,
    UNIQUE (trial_site_id, plot_number),
  
    UNIQUE (trial_site_id, treatment_id, replicate_number)
);


CREATE TABLE IF NOT EXISTS assessment_traits (
    trait_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id     INTEGER NOT NULL REFERENCES trials(trial_id) ON DELETE CASCADE,
    trait_name   TEXT NOT NULL,               
    label        TEXT,                        
    category     TEXT NOT NULL DEFAULT 'plant',  
    unit         TEXT,
    methodology  TEXT,
    min_value    REAL,                         
    max_value    REAL,
    UNIQUE (trial_id, trait_name)
);


CREATE TABLE IF NOT EXISTS assessment_data (
    data_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    plot_id          INTEGER NOT NULL REFERENCES plots(plot_id) ON DELETE CASCADE,
    trait_id         INTEGER NOT NULL REFERENCES assessment_traits(trait_id),
    assessment_date  TEXT NOT NULL,            
    numeric_value    REAL NOT NULL,
    collected_by     TEXT,
    synced           INTEGER NOT NULL DEFAULT 0,   
   
    UNIQUE (plot_id, trait_id, assessment_date)
);


CREATE TABLE IF NOT EXISTS plot_notes (
    note_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    plot_id    INTEGER NOT NULL REFERENCES plots(plot_id) ON DELETE CASCADE,
    note_date  TEXT NOT NULL,
    note_text  TEXT NOT NULL,
    UNIQUE (plot_id, note_date)
);
