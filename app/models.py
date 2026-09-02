from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(128))
    avatar_seed: Mapped[str] = mapped_column(String(64))
    system_prompt: Mapped[str] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="online")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    activities: Mapped[list["ActivityLog"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    title: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    agent: Mapped["Agent"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    agent: Mapped["Agent"] = relationship(back_populates="tasks")


class LinkedInDraft(Base):
    """LinkedIn drafts pending validation — persisted (was in-memory in V1)."""
    __tablename__ = "linkedin_drafts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    topic: Mapped[str] = mapped_column(String(256))
    angle: Mapped[str] = mapped_column(String(64), default="")
    author: Mapped[str] = mapped_column(String(32), default="marc")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    preview: Mapped[str] = mapped_column(Text, default="")
    full_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class NewsletterEdition(Base):
    """Editorial calendar — one row per monthly edition, editable from the UI."""
    __tablename__ = "newsletter_editions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number: Mapped[int] = mapped_column(Integer)
    season: Mapped[str] = mapped_column(String(8), index=True)          # s1 / s2 / s3
    season_label: Mapped[str] = mapped_column(String(64), default="")
    date: Mapped[str] = mapped_column(String(10))                       # ISO yyyy-mm-dd
    title: Mapped[str] = mapped_column(String(256))
    angle: Mapped[str] = mapped_column(Text, default="")
    edition_type: Mapped[str] = mapped_column(String(64), default="")
    format: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(16), default="planned")  # planned/draft/review/published
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class GenerationJob(Base):
    """Background generation job — lets the UI submit and poll instead of
    holding a 30s+ HTTP request open. Jobs interrupted by a restart are marked
    'error' at startup."""
    __tablename__ = "generation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), default="carousel")   # carousel | pipeline
    subject: Mapped[str] = mapped_column(String(256))
    payload: Mapped[str] = mapped_column(Text, default="{}")            # request JSON
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    # queued | running | done | error
    result: Mapped[str | None] = mapped_column(Text, nullable=True)     # response JSON
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BrandMemory(Base):
    """Brand memory document — single row, JSON payload.

    Replaces data/brand_memory.json: SQLite serialises writes, so concurrent
    generations can no longer clobber each other's updates.
    """
    __tablename__ = "brand_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    document: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    action: Mapped[str] = mapped_column(String(64))
    # `metadata` is reserved on SQLAlchemy Base; map a safe attribute name to the column.
    activity_metadata: Mapped[str] = mapped_column("metadata", Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    agent: Mapped["Agent"] = relationship(back_populates="activities")


# ============================================================================
# TPDL Lead Intelligence Pipeline — imported from scored_results.csv
# 38 source columns + a normalised sector_bucket + an import_run_id for
# month-over-month snapshot comparisons.
# ============================================================================

class Company(Base):
    __tablename__ = "companies"

    # Identity (Company Name is unique in the CSV; use as natural PK)
    name: Mapped[str] = mapped_column(String(256), primary_key=True)
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sector_bucket: Mapped[str] = mapped_column(String(32), default="Other", index=True)
    website: Mapped[str | None] = mapped_column(String(256), nullable=True)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    revenue: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Score block
    assessed_score: Mapped[float] = mapped_column(default=0.0, index=True)
    coverage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outreach_eligible: Mapped[bool] = mapped_column(default=False, index=True)

    # Narrative
    intelligence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Signal counts (Signals Found = int, Signals Not Evidenced = semicolon list)
    signals_found: Mapped[int] = mapped_column(default=0)
    signals_not_evidenced: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Signal 1
    s1_category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    s1_what_happened: Mapped[str | None] = mapped_column(Text, nullable=True)
    s1_why_it_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    s1_tpdl_relevance: Mapped[str | None] = mapped_column(String(128), nullable=True)
    s1_confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    s1_sources: Mapped[str | None] = mapped_column(Text, nullable=True)
    s1_urls: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Signal 2
    s2_category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    s2_what_happened: Mapped[str | None] = mapped_column(Text, nullable=True)
    s2_why_it_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    s2_tpdl_relevance: Mapped[str | None] = mapped_column(String(128), nullable=True)
    s2_confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    s2_sources: Mapped[str | None] = mapped_column(Text, nullable=True)
    s2_urls: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Signal 3
    s3_category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    s3_what_happened: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_why_it_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_tpdl_relevance: Mapped[str | None] = mapped_column(String(128), nullable=True)
    s3_confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    s3_sources: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_urls: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Context
    tech_stack_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    historical_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Flags
    icp_flag: Mapped[bool] = mapped_column(default=False, index=True)
    icp_flag_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_flag: Mapped[bool] = mapped_column(default=False, index=True)
    review_flag_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Human review (Vera's queue): null = not reviewed yet · "approved" / "rejected"
    review_status: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Run metadata
    run_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    import_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Signal(Base):
    """Normalised signal rows — one row per (company, slot).

    The Company s1_/s2_/s3_ columns mirror the CSV import 1:1 and stay as the
    staging area; this table is rebuilt from them at startup and after each
    import. All querying/filtering/aggregating goes through here — no more
    triple-OR over slot columns, and no 3-signal ceiling for future sources.
    """
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(ForeignKey("companies.name"), index=True)
    slot: Mapped[int] = mapped_column(Integer, default=1)
    category: Mapped[str] = mapped_column(String(64), index=True)
    what_happened: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_it_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    tpdl_relevance: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sources: Mapped[str | None] = mapped_column(Text, nullable=True)
    urls: Mapped[str | None] = mapped_column(Text, nullable=True)


class RunSnapshot(Base):
    """Per-run score snapshot — one row per (import_run_id, company).

    `companies` is overwritten in place on each import (only the latest run
    survives there). This APPEND-ONLY table keeps the history so Maya's
    `/recurring` and week-over-week trends can compare runs. Written by
    import_csv.py after each import; never updated.
    """
    __tablename__ = "run_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    import_run_id: Mapped[str] = mapped_column(String(64), index=True)
    company_name: Mapped[str] = mapped_column(String(256), index=True)
    assessed_score: Mapped[float] = mapped_column(default=0.0)
    coverage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outreach_eligible: Mapped[bool] = mapped_column(default=False)
    signals_found: Mapped[int] = mapped_column(default=0)
    run_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MegaCapRecap(Base):
    """One verbatim recap fact for the "top 10-15 mega-cap" trend-watch
    (pipeline/recap.py, `--recap` CLI mode). Distinct from `Signal`: this mode
    has NO scoring step (never Opus, never `assessed_score`) — it just files
    facts by category so Nathalie can see what changed at a mega-cap without
    it being pulled into the scored 620-company universe.

    One row per accepted recap evidence item (not one row per company),
    append-only — mirrors `RunSnapshot`'s per-run history pattern so a future
    trend view can compare runs. Written by `pipeline.recap.write_recap_rows`;
    never updated."""
    __tablename__ = "megacap_recaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(256), index=True)
    run_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    category: Mapped[str] = mapped_column(String(24))   # new_product|ma_activity|tech_platform|other
    summary_text: Mapped[str] = mapped_column(Text)      # deterministic, non-LLM (see recap.py)
    quote: Mapped[str] = mapped_column(Text)             # verbatim — audit trail
    source: Mapped[str] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    event_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Contact(Base):
    """Decision-maker contacts (CEO/CTO/CFO…) pulled via Apollo for shortlisted
    companies, with Inès's radar tags. One row per (company, person)."""
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(ForeignKey("companies.name"), index=True)
    full_name: Mapped[str] = mapped_column(String(128))
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str | None] = mapped_column(String(190), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # ── Inès radars ──
    language: Mapped[str] = mapped_column(String(8), default="en")     # "es" → Spanish radar fired
    lunch_campaign: Mapped[bool] = mapped_column(default=False)        # CH / Spain → in-person
    # ── Inès people-segmentation (derived from title + company score; see app/tools/segmentation.py) ──
    function: Mapped[str | None] = mapped_column(String(16), nullable=True)    # commercial | data | digital
    seniority: Mapped[str | None] = mapped_column(String(16), nullable=True)   # c_level | vp | director | other
    crm_segment: Mapped[int | None] = mapped_column(Integer, nullable=True)    # 1 warm | 2 active | 3 nurture
    premium: Mapped[bool] = mapped_column(default=False)              # Premium 5 → Andrés (human)
    status: Mapped[str] = mapped_column(String(24), default="new")    # new | queued_julie | handed_andres
    source: Mapped[str] = mapped_column(String(24), default="apollo")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ExecutiveMove(Base):
    """A detected executive-level role change in pharma/life-science — market
    intelligence on WHO moved WHERE, independent of whether either company is
    in the scored `companies` universe. One row per detected move.

    Chantier 4/4 of the 2026-09-01 Nathalie meeting recap (.claude/state.md).
    Slice 0 (this table + app/tools/exec_titles.py classifier) ships now;
    discovery/extraction (pipeline/exec_moves.py) and the /moves command
    surface (Inès review queue + Julie drafting) are NOT built yet — see
    state.md for the phasing. `status`/outreach fields exist from Slice 0 so
    later slices need no migration.

    NOT a Contact: Contact assumes the company is already scored and scoped
    to outreach for that company; this table is scoped to the PERSON and
    their career event, and may reference companies TPDL never scanned.

    ⚠️ GDPR (decision Betty, 2026-09-02): stores named individuals' career
    history (previous employer/title, move date) sourced from public press
    releases — more sensitive than Contact. Default retention policy:
    `dismissed` rows auto-purge after RETENTION_DAYS_DISMISSED days (see
    app/tools/exec_titles.py::purge_due). To CONFIRM with Andrés/Nathalie
    before any live discovery run (not blocking — this table has no live
    writer yet)."""
    __tablename__ = "executive_moves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Who / what happened (future verbatim-extraction output) ──
    person_name: Mapped[str] = mapped_column(String(128), index=True)
    new_title: Mapped[str] = mapped_column(String(160))
    new_company: Mapped[str] = mapped_column(String(256), index=True)
    # Free-text, NOT a real FK to companies.name — the new/previous employer is
    # very often NOT in the scored universe (that's the whole point of this
    # feature: it's industry-wide, not shortlist-derived). Resolved to a real
    # Company row only opportunistically via resolved_company_name below.
    previous_company: Mapped[str | None] = mapped_column(String(256), nullable=True)
    previous_title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    move_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # as stated in source; often month-precision only

    # ── Geography (for the 70/30 curation, app/tools/curation.py) ──
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)   # person/company HQ location, free text
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_company_name: Mapped[str | None] = mapped_column(
        ForeignKey("companies.name"), nullable=True, index=True)  # set IFF new_company matches a scored Company row

    # ── Role classification (deterministic — app/tools/exec_titles.py) ──
    seniority_tier: Mapped[str] = mapped_column(String(16))   # c_level | minus_1 | minus_2
    role_function: Mapped[str | None] = mapped_column(String(24), nullable=True)  # cmo|coo|cio|cto|chief_innovation|other

    # ── Evidence (verbatim lock — same doctrine as EvidenceItem, own schema) ──
    quote: Mapped[str] = mapped_column(Text)          # MUST appear verbatim in source_url's fetched text
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_type: Mapped[str] = mapped_column(String(16), default="news")  # news | press_release | linkedin

    # ── Review / workflow state (manual approve queue — not built yet) ──
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)
    # new → approved → connection_sent → follow_up_due → follow_up_sent → dismissed
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # GDPR retention clock

    # ── Outreach mechanic (not built yet — fields exist so no later migration) ──
    connection_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    connection_message: Mapped[str | None] = mapped_column(Text, nullable=True)   # drafted text, Julie/Andrés voice
    follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True)      # connection_sent_at + ~4 months, editable
    follow_up_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    follow_up_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Dedup / provenance ──
    dedup_key: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    # normalized "person_name|new_company|new_title" — prevents re-inserting the
    # same move if a weekly search surfaces the same press release twice.
    discovered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ============================================================================
# Collaborative workspace (Phase C) — users + per-company workflow state
# ============================================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64))
    avatar_seed: Mapped[str] = mapped_column(String(64))
    color: Mapped[str] = mapped_column(String(16), default="#0a0a0a")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CompanyAssignment(Base):
    """Single active claim per company. Insert-or-update on claim, delete on release."""
    __tablename__ = "company_assignments"

    company_name: Mapped[str] = mapped_column(ForeignKey("companies.name"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    claimed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CompanyStatus(Base):
    """Workflow state per company. One row per company; updated in place."""
    __tablename__ = "company_status"

    company_name: Mapped[str] = mapped_column(ForeignKey("companies.name"), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="new")
    # new / in_review / outreach_drafted / sent / replied / won / lost
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(ForeignKey("companies.name"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TeamActivity(Base):
    """Newest-first feed of who-did-what for the activity strip on /intel."""
    __tablename__ = "team_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(32))
    # claimed / released / status_changed / commented / generated_brief
    target_company: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    activity_metadata: Mapped[str] = mapped_column("metadata", Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


# ============================================================================
# Specialist output cache (Phase D minimum) — avoids re-calling Claude for
# the same company × specialist combination unless the user explicitly re-runs.
# ============================================================================

class SpecialistOutput(Base):
    __tablename__ = "specialist_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(ForeignKey("companies.name"), index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    output: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    generated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
