-- IN supabase form

-- 0. Remove the simple tables from the first version (this DELETES any data in them).
drop table if exists public.measurements cascade;
drop table if exists public.plots        cascade;
drop table if exists public.trials       cascade;

-- 1. Trials. user_id is the owner; it is filled in automatically from the logged-in user.
create table public.trials (
  trial_id      bigint generated always as identity primary key,
  user_id       uuid not null default auth.uid() references auth.users(id) on delete cascade,
  trial_code    text not null unique,                 -- e.g. TOM-BIO-2026-02
  trial_name    text,
  crop          text not null,
  variety       text,
  objective     text,
  planned_reps  integer not null default 3,
  start_date    date,
  end_date      date,
  status        text not null default 'active'
);

create table public.treatments (
  treatment_id         bigint generated always as identity primary key,
  trial_id             bigint not null references public.trials(trial_id) on delete cascade,
  treatment_name       text not null,
  formulation_details  text,
  unique (trial_id, treatment_name)
);

create table public.trial_sites (
  trial_site_id  bigint generated always as identity primary key,
  trial_id       bigint not null references public.trials(trial_id) on delete cascade,
  site_name      text not null,
  environment    text,
  unique (trial_id, site_name)
);

create table public.plots (
  plot_id           bigint generated always as identity primary key,
  trial_site_id     bigint not null references public.trial_sites(trial_site_id) on delete cascade,
  plot_number       integer not null,
  treatment_id      bigint not null references public.treatments(treatment_id),
  replicate_number  integer not null,
  unique (trial_site_id, plot_number),
  unique (trial_site_id, treatment_id, replicate_number)
);

create table public.assessment_traits (
  trait_id     bigint generated always as identity primary key,
  trial_id     bigint not null references public.trials(trial_id) on delete cascade,
  trait_name   text not null,
  label        text,
  category     text not null default 'plant',        -- plant | environment | quality
  unit         text,
  methodology  text,
  min_value    numeric,
  max_value    numeric,
  unique (trial_id, trait_name)
);

create table public.assessment_data (
  data_id          bigint generated always as identity primary key,
  plot_id          bigint not null references public.plots(plot_id) on delete cascade,
  trait_id         bigint not null references public.assessment_traits(trait_id),
  assessment_date  date not null,
  numeric_value    numeric not null,
  collected_by     text,
  unique (plot_id, trait_id, assessment_date)
);

create table public.plot_notes (
  note_id    bigint generated always as identity primary key,
  plot_id    bigint not null references public.plots(plot_id) on delete cascade,
  note_date  date not null,
  note_text  text not null,
  unique (plot_id, note_date)
);

-- Indexes for the foreign keys (Postgres does not add these automatically)
create index on public.treatments (trial_id);
create index on public.trial_sites (trial_id);
create index on public.plots (trial_site_id);
create index on public.plots (treatment_id);
create index on public.assessment_traits (trial_id);
create index on public.assessment_data (plot_id);
create index on public.assessment_data (trait_id);
create index on public.plot_notes (plot_id);

-- 2. Row Level Security: a user can only see and change rows that belong to their own trials.
alter table public.trials            enable row level security;
alter table public.treatments        enable row level security;
alter table public.trial_sites       enable row level security;
alter table public.plots             enable row level security;
alter table public.assessment_traits enable row level security;
alter table public.assessment_data   enable row level security;
alter table public.plot_notes        enable row level security;

create policy "own trials" on public.trials for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy "own treatments" on public.treatments for all to authenticated
  using (exists (select 1 from public.trials t where t.trial_id = treatments.trial_id and t.user_id = auth.uid()))
  with check (exists (select 1 from public.trials t where t.trial_id = treatments.trial_id and t.user_id = auth.uid()));

create policy "own sites" on public.trial_sites for all to authenticated
  using (exists (select 1 from public.trials t where t.trial_id = trial_sites.trial_id and t.user_id = auth.uid()))
  with check (exists (select 1 from public.trials t where t.trial_id = trial_sites.trial_id and t.user_id = auth.uid()));

create policy "own traits" on public.assessment_traits for all to authenticated
  using (exists (select 1 from public.trials t where t.trial_id = assessment_traits.trial_id and t.user_id = auth.uid()))
  with check (exists (select 1 from public.trials t where t.trial_id = assessment_traits.trial_id and t.user_id = auth.uid()));

create policy "own plots" on public.plots for all to authenticated
  using (exists (select 1 from public.trial_sites s join public.trials t on t.trial_id = s.trial_id
                 where s.trial_site_id = plots.trial_site_id and t.user_id = auth.uid()))
  with check (exists (select 1 from public.trial_sites s join public.trials t on t.trial_id = s.trial_id
                      where s.trial_site_id = plots.trial_site_id and t.user_id = auth.uid()));

create policy "own data" on public.assessment_data for all to authenticated
  using (exists (select 1 from public.plots p join public.trial_sites s on s.trial_site_id = p.trial_site_id
                 join public.trials t on t.trial_id = s.trial_id
                 where p.plot_id = assessment_data.plot_id and t.user_id = auth.uid()))
  with check (exists (select 1 from public.plots p join public.trial_sites s on s.trial_site_id = p.trial_site_id
                      join public.trials t on t.trial_id = s.trial_id
                      where p.plot_id = assessment_data.plot_id and t.user_id = auth.uid()));

create policy "own notes" on public.plot_notes for all to authenticated
  using (exists (select 1 from public.plots p join public.trial_sites s on s.trial_site_id = p.trial_site_id
                 join public.trials t on t.trial_id = s.trial_id
                 where p.plot_id = plot_notes.plot_id and t.user_id = auth.uid()))
  with check (exists (select 1 from public.plots p join public.trial_sites s on s.trial_site_id = p.trial_site_id
                      join public.trials t on t.trial_id = s.trial_id
                      where p.plot_id = plot_notes.plot_id and t.user_id = auth.uid()));

-- 3. Make Supabase pick up the new tables straight away
notify pgrst, 'reload schema';
