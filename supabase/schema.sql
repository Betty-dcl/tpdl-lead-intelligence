-- ============================================================================
-- TPDL AI Team — Supabase schema
-- Paste this entire file into Supabase → SQL Editor → New query → Run.
-- Idempotent: safe to re-run (uses IF NOT EXISTS / CREATE OR REPLACE).
-- ============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- DOMAIN 1 — Agents & traceability
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists agents (
  id            text primary key,
  name          text not null,
  role          text not null,
  team          text not null default 'management',  -- intel | marketing | management
  avatar_seed   text not null,
  color         text not null default '#0a0a0a',
  status        text not null default 'online',
  system_prompt text,
  created_at    timestamptz not null default now()
);

create table if not exists users (
  id            bigint generated always as identity primary key,
  username      text unique not null,
  display_name  text not null,
  avatar_seed   text not null,
  color         text not null default '#0a0a0a',
  created_at    timestamptz not null default now()
);

create table if not exists agent_activity (
  id           bigint generated always as identity primary key,
  agent_id     text references agents(id) on delete cascade,
  user_id      bigint references users(id) on delete set null,
  action       text not null,
  target_type  text,                 -- company | content_piece | conversation | ...
  target_id    text,
  metadata     jsonb not null default '{}'::jsonb,
  created_at   timestamptz not null default now()
);
create index if not exists idx_agent_activity_created on agent_activity(created_at desc);
create index if not exists idx_agent_activity_agent   on agent_activity(agent_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- DOMAIN 2 — Market Intelligence (scraping + interpreted)
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists companies (
  name                  text primary key,
  sector                text,
  sector_bucket         text not null default 'Other',
  website               text,
  location              text,
  revenue               text,
  assessed_score        double precision not null default 0,
  coverage              text,
  outreach_eligible     boolean not null default false,
  intelligence_summary  text,
  signals_found         int not null default 0,
  tech_stack_summary    text,
  historical_context    text,
  icp_flag              boolean not null default false,
  review_flag           boolean not null default false,
  import_run_id         text,
  run_date              timestamptz,
  imported_at           timestamptz not null default now()
);
create index if not exists idx_companies_score  on companies(assessed_score desc);
create index if not exists idx_companies_bucket  on companies(sector_bucket);

create table if not exists signals (
  id              bigint generated always as identity primary key,
  company_name    text references companies(name) on delete cascade,
  category        text,                 -- leadership_change | hiring | ma_expansion | ...
  what_happened   text,
  why_it_matters  text,
  tpdl_relevance  text,
  confidence      text,
  sources         jsonb not null default '[]'::jsonb,
  urls            jsonb not null default '[]'::jsonb,
  created_at      timestamptz not null default now()
);
create index if not exists idx_signals_company  on signals(company_name);
create index if not exists idx_signals_category on signals(category);

create table if not exists scrape_results (
  id           bigint generated always as identity primary key,
  agent_id     text references agents(id) on delete set null,
  query        text not null,
  raw_results  jsonb not null default '[]'::jsonb,
  source       text,                    -- duckduckgo | linkedin | rss | ...
  created_at   timestamptz not null default now()
);

create table if not exists insights (
  id                bigint generated always as identity primary key,
  agent_id          text references agents(id) on delete set null,
  scrape_result_id  bigint references scrape_results(id) on delete cascade,
  summary           text,
  interpreted_data  jsonb not null default '{}'::jsonb,
  created_at        timestamptz not null default now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- DOMAIN 3 — Content production
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists content_pieces (
  id               bigint generated always as identity primary key,
  subject          text not null,
  angle            text,
  status           text not null default 'draft',   -- draft|review|approved|published
  created_by_agent text references agents(id) on delete set null,
  source           text not null default 'manual',  -- manual|pipeline|veille
  web_enriched     boolean not null default false,
  created_at       timestamptz not null default now()
);
create index if not exists idx_content_pieces_status on content_pieces(status);

create table if not exists content_formats (
  id                bigint generated always as identity primary key,
  content_piece_id  bigint references content_pieces(id) on delete cascade,
  format            text not null,        -- linkedin|pdf_a4|website|ppt
  body              text,
  status            text not null default 'draft',
  tokens            int,
  produced_by_agent text references agents(id) on delete set null,
  created_at        timestamptz not null default now()
);
create index if not exists idx_content_formats_piece on content_formats(content_piece_id);

create table if not exists veille_runs (
  id                     bigint generated always as identity primary key,
  agent_id               text references agents(id) on delete set null,
  subjects               jsonb not null default '[]'::jsonb,
  search_context_length  int,
  trigger                text not null default 'auto',   -- auto|manual
  ran_at                 timestamptz not null default now()
);

create table if not exists pipeline_runs (
  id            bigint generated always as identity primary key,
  subject       text not null,
  formats       jsonb not null default '[]'::jsonb,
  auto_subject  boolean not null default false,
  status        text not null default 'done',
  iris_output   text,
  created_at    timestamptz not null default now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- DOMAIN 4 — Publication & marketing results
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists publications (
  id                 bigint generated always as identity primary key,
  content_format_id  bigint references content_formats(id) on delete cascade,
  channel            text not null,       -- linkedin|newsletter|website
  external_url       text,
  status             text not null default 'scheduled',  -- scheduled|published|failed
  published_at       timestamptz,
  created_at         timestamptz not null default now()
);

create table if not exists post_metrics (
  id              bigint generated always as identity primary key,
  publication_id  bigint references publications(id) on delete cascade,
  impressions     int not null default 0,
  engagement_rate double precision not null default 0,
  clicks          int not null default 0,
  captured_at     timestamptz not null default now()
);

create table if not exists newsletter_editions (
  id              bigint generated always as identity primary key,
  number          int,
  season          text,
  title           text,
  angle           text,
  format          text,
  scheduled_date  date,
  status          text not null default 'planned',
  created_at      timestamptz not null default now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- DOMAIN 5 — Collaboration & dashboard
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists conversations (
  id          bigint generated always as identity primary key,
  agent_id    text references agents(id) on delete cascade,
  user_id     bigint references users(id) on delete set null,
  title       text not null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table if not exists messages (
  id               bigint generated always as identity primary key,
  conversation_id  bigint references conversations(id) on delete cascade,
  role             text not null,        -- user|assistant|system
  content          text not null,
  created_at       timestamptz not null default now()
);
create index if not exists idx_messages_conv on messages(conversation_id);

create table if not exists company_assignments (
  company_name  text primary key references companies(name) on delete cascade,
  user_id       bigint references users(id) on delete cascade,
  claimed_at    timestamptz not null default now()
);

create table if not exists company_status (
  company_name        text primary key references companies(name) on delete cascade,
  status              text not null default 'new',
  updated_by_user_id  bigint references users(id) on delete set null,
  updated_at          timestamptz not null default now()
);

create table if not exists comments (
  id            bigint generated always as identity primary key,
  company_name  text references companies(name) on delete cascade,
  user_id       bigint references users(id) on delete set null,
  content       text not null,
  created_at    timestamptz not null default now()
);
create index if not exists idx_comments_company on comments(company_name);

-- ─────────────────────────────────────────────────────────────────────────────
-- DOMAIN 6 — Brand memory
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists brand_voice (
  id          int primary key default 1,
  tone        text,
  audience    text,
  avoid       jsonb not null default '[]'::jsonb,
  structure   text,
  examples    jsonb not null default '[]'::jsonb,
  updated_at  timestamptz not null default now(),
  constraint brand_voice_singleton check (id = 1)
);

create table if not exists treated_subjects (
  id       bigint generated always as identity primary key,
  subject  text not null,
  formats  jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists content_feedback (
  id                bigint generated always as identity primary key,
  content_format_id bigint references content_formats(id) on delete cascade,
  decision          text not null,       -- approved|rejected
  user_id           bigint references users(id) on delete set null,
  created_at        timestamptz not null default now()
);

-- ============================================================================
-- REALTIME — add tables to the realtime publication
-- ============================================================================
alter publication supabase_realtime add table agent_activity;
alter publication supabase_realtime add table content_formats;
alter publication supabase_realtime add table content_pieces;
alter publication supabase_realtime add table messages;
alter publication supabase_realtime add table company_status;
alter publication supabase_realtime add table company_assignments;
alter publication supabase_realtime add table comments;
alter publication supabase_realtime add table veille_runs;
alter publication supabase_realtime add table pipeline_runs;

-- ============================================================================
-- DONE. Next: run schema_rls.sql for security policies, then seed_agents.sql.
-- ============================================================================
