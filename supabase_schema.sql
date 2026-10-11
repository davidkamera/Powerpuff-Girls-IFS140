-- AgriTrial OS - Supabase (cloud) table.
-- Run this once in the Supabase dashboard: SQL Editor -> New query -> paste -> Run.
--
-- The brief asks for ONE cloud table of aggregated trial data, so the three local
-- SQLite tables are flattened into a single row per plot.

create table if not exists public.trial_data (
    record_id         text primary key,
    trial_code        text not null,
    plot_id           integer not null,
    date              date not null,
    site              text not null,
    environment       text,
    crop              text not null,
    variety           text,
    treatment_group   text not null,
    rep_number        integer not null,
    trial_week        integer,
    observer          text,
    field_notes       text,

    height_cm         double precision,
    leaf_count        integer,
    fresh_weight_g    double precision,
    dry_weight_g      double precision,
    chlorophyll_spad  double precision,
    root_mass_g       double precision,
    yield_value       double precision,   -- kg/plot
    disease_pct       double precision,

    ph                double precision,
    ec_mscm           double precision,
    dissolved_o2      double precision,
    temp_c            double precision,
    humidity_pct      double precision,
    nitrate_mgl       double precision,
    phosphate_mgl     double precision,

    synced_at         timestamptz default now(),

    unique (trial_code, treatment_group, rep_number, date)
);

-- Row Level Security on: the public (anon) key cannot read or write this table.
-- The Python backend uses the service_role key, which bypasses RLS.
-- Keep that key in .env only - never in the frontend or on GitHub.
alter table public.trial_data enable row level security;
