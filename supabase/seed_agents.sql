-- ============================================================================
-- TPDL AI Team — seed the 10 agents + 5 team users.
-- Run AFTER schema.sql. Idempotent (upsert on conflict).
-- NOTE: system_prompt is left NULL here — the FastAPI backend owns the prompts
-- (seed.py). This just guarantees the rows exist for the dashboard + FKs.
-- ============================================================================

insert into agents (id, name, role, team, avatar_seed, color) values
  ('manager','Alex','Team Manager','management','manager-alex','#0a0a0a'),
  ('hugo','Hugo','Leadership Transitions','intel','hugo-tpdl-leadership','#6366f1'),
  ('maya','Maya','Hiring Signals','intel','maya-tpdl-hiring','#10B981'),
  ('diego','Diego','M&A / Expansion','intel','diego-tpdl-mna','#8B5CF6'),
  ('eva','Eva','PE Events','intel','eva-tpdl-pe','#0EA5E9'),
  ('kai','Kai','Digital Initiatives','intel','kai-tpdl-digital','#f97316'),
  ('sofia','Sofia','Org Restructuring','intel','sofia-tpdl-restructure','#d946ef'),
  ('iris','Iris','Research & Trends','marketing','iris-tpdl-marketing-intel','#14b8a6'),
  ('marcus','Marcus','Content Architect','marketing','marcus-tpdl-linkedin','#F59E0B'),
  ('nina','Nina','Format Producer','marketing','nina-tpdl-casestudies','#EC4899')
on conflict (id) do update set
  name = excluded.name,
  role = excluded.role,
  team = excluded.team,
  avatar_seed = excluded.avatar_seed,
  color = excluded.color;

insert into users (username, display_name, avatar_seed, color) values
  ('marie','Marie','marie-user','#1E3A8A'),
  ('pierre','Pierre','pierre-user','#10B981'),
  ('sophie','Sophie','sophie-user','#8B5CF6'),
  ('lea','Léa','lea-user','#F59E0B'),
  ('tomas','Tomás','tomas-user','#EC4899')
on conflict (username) do nothing;

-- Brand voice singleton
insert into brand_voice (id, tone, audience, avoid, structure) values
  (1,
   'Analytical, direct, data-driven. No corporate jargon. UK English.',
   'VP and C-suite in European pharma, medtech, dental companies.',
   '["AI hype","buzzwords","generic advice","passive voice"]'::jsonb,
   'Strong hook -> concrete data point -> TPDL angle -> clear CTA.')
on conflict (id) do nothing;
