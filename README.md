# AI Consulting Firm

A local web platform that simulates a team of 6 AI employees for a consulting firm.

| Agent | Role |
|---|---|
| **Alex** | Team Manager — single entry point, routes requests to the right specialist |
| **Sarah** | Market Intelligence Lead — detects target companies and their signals |
| **Lea** | ICP Analyst — scores companies and interprets why they need you |
| **Marcus** | LinkedIn Content Strategist — drafts posts |
| **Tom** | Outreach Copywriter — writes personalised outbound emails |
| **Nina** | Case Studies & Deck Designer — structures case studies |

## What you can do today (V1)

- **Open Space** (`/`): chat with Alex; he routes you to the right specialist with a `[ROUTE_TO: x]` tag that the UI turns into a clickable hand-off. Click any teammate's card to chat directly. Each specialist also exposes a slash command that pulls mock market data and asks Claude to format it.
- **Marketing** (`/marketing`): LinkedIn drafts to approve/reject, daily impressions chart, case studies list, website pages with mocked SEO scores, outreach pipeline + ICP templates.
- **Market Intel** (`/intel`): 17 detected companies sortable & filterable, signals timeline, 3 charts (detections per week / sector distribution / ICP over time).
- **Agent profile** (`/agent/<id>`): full conversation history with inline message viewer + activity feed.

## Stack
- **Backend**: FastAPI + SQLAlchemy 2.0 + SQLite (file at `data/app.db`)
- **Frontend**: HTML + Tailwind (CDN) + Alpine.js (CDN) + Chart.js (CDN) — no build step
- **LLM**: Claude (default `claude-sonnet-4-5`) via the official `anthropic` SDK

## Setup

```bash
# 1. Create venv, install deps, seed the DB
make setup

# 2. Add your Anthropic API key
$EDITOR .env    # set ANTHROPIC_API_KEY=sk-ant-...

# 3. Run the server
make run

# Open http://localhost:8000
```

Or without Make:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # edit ANTHROPIC_API_KEY
python seed.py
uvicorn app.main:app --reload --port 8000
```

> **Python version**: 3.10+ works. The brief targeted 3.11+; the code only uses 3.10 features (`X | None` syntax).

### Make targets
- `make setup` — venv + deps + `.env` + seed
- `make run` — server on PORT=8000 (override with `make run PORT=8080`)
- `make seed` — re-seed agents (idempotent — updates in place)
- `make check` — quick import smoke test (catches syntax errors before run)
- `make clean` — delete the SQLite DB
- `make fresh` — clean + setup

## First-run walkthrough

Once the server is up and your API key is set, try this 5-minute tour:

1. **Talk to Alex** on the Open Space:
   > "Find me PE firms in France that just hired a new Managing Partner"

   He routes to Sarah; click **→ Continue with Sarah** — her drawer opens.
2. **In Sarah's drawer, type** `/scan` → she returns 3 mock companies in her strict format. Her card on the Open Space updates with `just now · ran a market scan`.
3. **Open Lea's drawer**, type `/score Helio Capital` → she scores the company and proposes an attack angle.
4. **Open Tom's drawer**, type `/email Helio Capital` → he drafts a personalised outbound mail referencing the company's recent signal.
5. **Open Marcus's drawer**, type `/draft_post AI in due diligence` → 2 LinkedIn post variations.
6. **Open Nina's drawer**, type `/case_study Acme Corp` → a 6-slide case-study structure.
7. **Visit `/marketing`** → approve or reject Marcus's pending drafts, browse case studies, watch the engagement chart.
8. **Visit `/intel`** → filter the companies table, click **Brief by Lea** on any row (her drawer opens with `/score <company>` pre-filled — just hit Send).
9. **Visit `/agent/sarah`** (or any agent profile) → review past conversations and the activity feed.

## Slash command cheatsheet

| Agent | Command | Effect |
|---|---|---|
| Sarah | `/scan [sector?]` | Pulls 3 mock companies (optionally filtered by sector substring) and asks Sarah to format them. |
| Lea | `/score <company>` | Looks the company up in mocks; injects facts + ICP reference; Lea applies her scoring format. Friendly handling for missing/unknown company. |
| Marcus | `/draft_post <topic>` | Tagged as a task; Claude generates 2 post variations. |
| Tom | `/email <company>` | Looks the company up; injects facts; Tom's first sentence references the recent signal. |
| Nina | `/case_study <client>` | Tagged as a task; Claude structures a 6-slide deck. |

The looser commands in each agent's prompt (`/signals`, `/icp`, `/voice`, `/calendar`, `/inmail`, `/sequence`, `/proposal_template`, `/slide_outline`) pass through to Claude with no backend augmentation — the system prompt tells him how to handle them.

## Project structure

```
.
├── app/
│   ├── main.py              FastAPI app, lifespan, static mount, 404 + favicon
│   ├── config.py            Settings + AgentID enum + directory constants
│   ├── database.py          SQLAlchemy engine + session
│   ├── models.py            5 ORM models (agents, conversations, messages, tasks, activity_log)
│   ├── schemas.py           Pydantic I/O schemas
│   ├── activity_labels.py   Action codes → UI labels
│   ├── agents/
│   │   ├── base.py          BaseAgent: persist, call Claude, dispatch slash commands
│   │   ├── manager.py       (thin — uses BaseAgent unchanged)
│   │   ├── sarah.py         /scan
│   │   ├── lea.py           /score
│   │   ├── marcus.py        /draft_post
│   │   ├── tom.py           /email
│   │   └── nina.py          /case_study
│   ├── routers/
│   │   ├── pages.py         HTML pages: /, /marketing, /intel, /agent/{id}
│   │   ├── chat.py          POST /api/chat/{agent_id}
│   │   ├── agents.py        GET /api/agents (+latest activity), /{id}, /{id}/conversations, /{id}/activity
│   │   ├── conversations.py GET /api/conversations/{id}/messages
│   │   ├── marketing.py     /api/marketing/* (LinkedIn drafts + KPIs + case studies + website + outreach)
│   │   └── intel.py         /api/intel/* (companies + signals + stats)
│   └── mocks/
│       ├── companies.py        17 target companies with ICP scores
│       ├── linkedin_drafts.py  5 Marcus posts pending validation (in-memory state)
│       ├── marketing.py        KPIs, engagement series, case studies, website pages, outreach
│       └── intel.py            Sector buckets + weekly time series for the charts
├── static/
│   ├── css/custom.css
│   └── js/
│       ├── office.js        Open Space — Alpine stores + drawer chat + ?drawer/?prefill deep links
│       ├── agent_profile.js Profile page
│       ├── marketing.js     Marketing dashboard + Chart.js
│       └── intel.js         Market Intel dashboard + Chart.js
├── templates/
│   ├── base.html
│   ├── office.html
│   ├── marketing.html
│   ├── intel.html
│   ├── agent_profile.html
│   └── 404.html
├── data/
│   └── app.db               SQLite (created at first run)
├── seed.py                  Populates agents table with English system prompts
├── requirements.txt
├── .env.example
├── Makefile
├── INSTRUCTIONS.md          Original brief (French)
├── AGENTS.md                Original agent personas spec (French)
└── README.md                (this file)
```

## API reference

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/chat/{agent_id}` | Send a message; returns assistant reply + optional `routed_to` (Manager only). |
| GET | `/api/agents` | All 6 agents, each with `last_activity_label` + `last_activity_at`. |
| GET | `/api/agents/{id}` | Single agent. |
| GET | `/api/agents/{id}/conversations` | Conversations with `message_count`, newest first. |
| GET | `/api/agents/{id}/activity?limit=20` | Latest activities (with parsed metadata). |
| GET | `/api/conversations/{id}/messages` | Full message thread. |
| GET | `/api/marketing/linkedin/drafts?status=pending` | Filter by `pending`/`approved`/`rejected`/`all`. |
| POST | `/api/marketing/linkedin/drafts/{id}/approve` | Mark draft approved. |
| POST | `/api/marketing/linkedin/drafts/{id}/reject` | Mark draft rejected. |
| GET | `/api/marketing/linkedin/metrics` | KPIs + 30-day daily impressions series. |
| GET | `/api/marketing/case-studies` | Case studies list. |
| GET | `/api/marketing/website-pages` | Website pages with SEO score. |
| GET | `/api/marketing/outreach` | Outreach pipeline + ICP templates. |
| GET | `/api/intel/companies?country=&size=&sector=&signal_type=` | All 17 companies, default sort ICP desc, optional substring filters. |
| GET | `/api/intel/signals?limit=50` | Flat signals timeline, newest first. |
| GET | `/api/intel/stats` | The 3 chart series. |
| GET | `/healthz` | Health check. |

API errors return `{"detail": "..."}` with a sensible HTTP status (404 for missing resources, 422 for validation, 502 when the Claude call fails).

## Deep links

The Open Space supports two query params so other pages can hand off cleanly:
- `/?drawer=<id>` — opens that specialist's drawer on load
- `/?drawer=<id>&prefill=<text>` — also pre-fills the chat input

Used by:
- Marketing's `+ Brief Marcus`, `+ Brief Tom`, `+ New case study with Nina` buttons
- Market Intel's `+ Ask Sarah for a new scan` (`?drawer=sarah&prefill=/scan`) and per-row `Brief by Lea` (`?drawer=lea&prefill=/score <company>`)

## What's mocked (V1) → real (V2 roadmap)

| V1 (mock) | V2 (planned) |
|---|---|
| 17 hardcoded companies in `app/mocks/companies.py` | Live feed from LinkedIn / Crunchbase / news APIs |
| In-memory LinkedIn drafts list (resets on restart) | `tasks` rows linked to Marcus's `/draft_post` calls + LinkedIn API publishing |
| Hardcoded engagement & SEO scores | Real LinkedIn analytics + SEO tool integration |
| Outreach pipeline as a static list | Gmail/Outlook integration; track sends and replies |
| `/case_study` returns structured text only | Generate real `.pptx` via the Beyond template |
| Single-user, no auth | Multi-tenant + auth |

## Troubleshooting

**"<Agent> could not respond — ANTHROPIC_API_KEY is not set"**
Fill in your API key in `.env` and restart: `make run`.

**The team cards say "No activity yet" after a chat turn**
The cards refresh after every successful exchange. If you have the page open from before the server was reseeded, hit reload.

**Port 8000 is already in use**
`make run PORT=8080` — or any free port.

**Lost my database / want to start over**
`make fresh` deletes `data/app.db` and re-seeds the agents. Note that conversations, tasks and activity rows aren't seeded — they're only created by real interactions.

**Drafts I approved came back after restart**
Intentional in V1 — the LinkedIn drafts state is in-memory, not persisted. V2 will tie drafts to `tasks` rows.

## Original brief

See [INSTRUCTIONS.md](INSTRUCTIONS.md) (French) for the original 7-phase build spec and [AGENTS.md](AGENTS.md) for the original agent personas (French). The implementation translated agent system prompts to English and renamed Léa → **Lea**; everything else follows the spec.
