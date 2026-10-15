// API layer over Supabase's auto-generated REST endpoints (schema_postgres.sql).
// Usage: const api = createApi(supabaseClient);  await api.trials.list();

function createApi(sb) {
  const unwrap = ({ data, error }) => {
    if (error) throw new Error(error.message);
    return data;
  };
  const insert = (table) => (row) => sb.from(table).insert(row).select().single().then(unwrap);
  const remove = (table, key) => (id) => sb.from(table).delete().eq(key, id).then(unwrap);
  const forTrial = (table, order) => (trialId) =>
    sb.from(table).select('*').eq('trial_id', trialId).order(order).then(unwrap);

  return {
    trials: {
      list: () => sb.from('trials').select('*').order('trial_id', { ascending: false }).then(unwrap),
      create: insert('trials'),                 // user_id is filled in by the database
      remove: remove('trials', 'trial_id'),
    },
    sites: {
      listForTrial: forTrial('trial_sites', 'site_name'),
      create: insert('trial_sites'),
      remove: remove('trial_sites', 'trial_site_id'),
    },
    treatments: {
      listForTrial: forTrial('treatments', 'treatment_name'),
      create: insert('treatments'),
      remove: remove('treatments', 'treatment_id'),
    },
    traits: {
      listForTrial: forTrial('assessment_traits', 'trait_name'),
      create: insert('assessment_traits'),
      remove: remove('assessment_traits', 'trait_id'),
    },
    plots: {
      listForTrial: (trialId) =>
        sb.from('plots')
          .select('*, trial_sites!inner(site_name, trial_id), treatments(treatment_name)')
          .eq('trial_sites.trial_id', trialId)
          .order('plot_number').then(unwrap),
      create: insert('plots'),
      remove: remove('plots', 'plot_id'),
    },
    readings: {
      listForTrial: (trialId) =>
        sb.from('assessment_data')
          .select('*, assessment_traits!inner(trait_name, unit, trial_id), plots(plot_number)')
          .eq('assessment_traits.trial_id', trialId)
          .order('assessment_date', { ascending: false }).then(unwrap),
      create: insert('assessment_data'),
      remove: remove('assessment_data', 'data_id'),
    },
  };
}