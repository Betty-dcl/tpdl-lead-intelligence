-- ============================================================================
-- TPDL AI Team — Row Level Security
-- Run AFTER schema.sql.
--
-- Model:
--   • service_role key (FastAPI backend) bypasses RLS entirely → full access.
--   • anon key (frontend) gets READ-ONLY on the tables the dashboard displays.
--   • NO direct writes from the frontend — every write goes through FastAPI,
--     which validates and uses the service_role key.
--
-- This keeps the Anthropic API key server-side and prevents tampering.
-- ============================================================================

-- Enable RLS on every table
alter table agents               enable row level security;
alter table users                enable row level security;
alter table agent_activity       enable row level security;
alter table companies            enable row level security;
alter table signals              enable row level security;
alter table scrape_results       enable row level security;
alter table insights             enable row level security;
alter table content_pieces       enable row level security;
alter table content_formats      enable row level security;
alter table veille_runs          enable row level security;
alter table pipeline_runs        enable row level security;
alter table publications         enable row level security;
alter table post_metrics         enable row level security;
alter table newsletter_editions  enable row level security;
alter table conversations        enable row level security;
alter table messages             enable row level security;
alter table company_assignments  enable row level security;
alter table company_status       enable row level security;
alter table comments             enable row level security;
alter table brand_voice          enable row level security;
alter table treated_subjects     enable row level security;
alter table content_feedback     enable row level security;

-- ─────────────────────────────────────────────────────────────────────────────
-- READ-ONLY policies for the anon role (frontend dashboard + realtime).
-- We expose only what the dashboard needs to display. Sensitive columns like
-- agents.system_prompt are read too — if you want to hide it, drop that grant.
-- ─────────────────────────────────────────────────────────────────────────────

do $$
declare
  t text;
  readable_tables text[] := array[
    'agents','users','agent_activity','companies','signals',
    'content_pieces','content_formats','veille_runs','pipeline_runs',
    'publications','post_metrics','newsletter_editions',
    'conversations','messages','company_assignments','company_status',
    'comments','brand_voice','treated_subjects','content_feedback'
  ];
begin
  foreach t in array readable_tables loop
    execute format('drop policy if exists "anon_read_%s" on %I;', t, t);
    execute format(
      'create policy "anon_read_%s" on %I for select to anon using (true);',
      t, t
    );
  end loop;
end $$;

-- scrape_results + insights stay backend-only (no anon read) — raw scrape data.

-- ============================================================================
-- NOTE: no INSERT / UPDATE / DELETE policies for anon → all writes blocked
-- for the frontend. The FastAPI backend uses the service_role key, which
-- bypasses RLS, so it can write freely. This is the intended security model.
-- ============================================================================
