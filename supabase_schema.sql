-- AgriTrial OS - Supabase (cloud) table, version 2.
-- Run once in the Supabase dashboard: SQL Editor -> New query -> paste -> Run.
--
-- The brief asks for ONE cloud table of aggregated trial data. Following the lecturer's
-- vertical design, it holds one row per reading, so any crop or test fits without
-- adding columns. Reports and dashboards pivot it into columns when they need to.

create table if not exists public.trial_measurements (
    trial_code       text not null,
    crop             text not null,
    variety          text,
    site_name        text not null,
    plot_number      integer not null,
    treatment_name   text not null,
    replicate_number integer not null,
    trait_name       text not null,
    unit             text,
    assessment_date  date not null,
    numeric_value    double precision not null,
    collected_by     text,
    field_notes      text,
    synced_at        timestamptz default now(),

    -- the same reading is never stored twice; syncing again updates it
    primary key (trial_code, site_name, plot_number, trait_name, assessment_date)
);

-- Row Level Security on: the public key cannot read or write this table.
-- The Python backend uses the secret (service_role) key, which bypasses RLS.
-- Keep that key in .env only - never in the frontend or on GitHub.
alter table public.trial_measurements enable row level security;

-- Optional: remove the version 1 table (10 sample rows) if you created it earlier.
-- drop table if exists public.trial_data;
