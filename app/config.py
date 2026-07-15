from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"


class AgentID(str, Enum):
    MANAGER = "manager"
    # ── Sales / Outbound Intelligence pipeline ──
    HUGO = "hugo"      # Deep Research & Scoring
    MAYA = "maya"      # Analyst — Top 50/100 + recurring trends
    INES = "ines"      # Contacts (Apollo) & Radars
    JULIE = "julie"    # Sector-segmented outreach
    # ── Marketing Intelligence pipeline ──
    IRIS = "iris"      # Marketing research + trend scoring (Hugo+Maya mix)
    MARC = "marc"      # Content Architect
    OLIVER = "oliver"  # Format Producer
    # ── Quality / oversight (cross-cutting, not a pipeline step) ──
    VERA = "vera"      # Verification — QA at every handoff + human review queue


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = "not-set"
    # Chat agents (dashboard) run on Opus 4.8. The pipeline's two-model split
    # (Sonnet 5 extraction / Opus 4.8 interpretation) lives in the engine, not here.
    anthropic_model: str = "claude-opus-4-8"
    port: int = 8000
    # On Railway, set DATABASE_URL env var to point to the mounted volume:
    # sqlite:////data/app.db  (absolute path to /data volume)
    database_url: str = "sqlite:///./data/app.db"
    # DATA_DIR lets memory.py + seed.py write to the right place in prod
    data_dir: str = "./data"

    # ── Supabase (optional) ──────────────────────────────────────────────
    # When all three are set, the app uses Supabase (Postgres + realtime).
    # When empty, it falls back to local SQLite — nothing breaks.
    supabase_url: str = ""              # https://xxxx.supabase.co  (public)
    supabase_anon_key: str = ""         # public — injected into frontend
    supabase_service_key: str = ""      # 🔴 SECRET — server-side only

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)

    # Set true in production (Railway is HTTPS) so session cookies are
    # never sent over plain HTTP. Keep false for local dev.
    session_https_only: bool = False

    # ── OneDrive shared CSV (optional) ───────────────────────────────────
    # Paste the team's OneDrive "anyone with the link can view" URL here.
    # The platform downloads + parses it on demand (Refresh button).
    onedrive_csv_url: str = ""

    # ── Hugo — Lead Intelligence Pipeline research engines ───────────────
    # Keys for the 8-source deep-research stack. Empty = that engine is
    # disabled (Hugo still reads the already-scored universe in the DB).
    # Provided by TPDL later; see TPDL_Pipeline_Documentation.
    exa_api_key: str = ""          # Exa neural search (Steps: general/leadership/M&A)
    perplexity_api_key: str = ""   # Perplexity Sonar (financial press: M&A/PE)
    serpapi_key: str = ""          # SerpAPI (Google News + Google Jobs)
    apify_token: str = ""          # Apify / Wappalyzer actor (tech-stack scan)
    firecrawl_api_key: str = ""    # Firecrawl (IR/website page fetch)

    # ── Inès — Apollo.io (decision-maker contacts) ──────────────────────
    apollo_api_key: str = ""       # Apollo people/search — CEO/CTO/CFO + LinkedIn

    @property
    def research_engines_ready(self) -> bool:
        """True when Hugo can run a live pipeline re-run (not just read the DB)."""
        return bool(self.exa_api_key and self.perplexity_api_key and self.serpapi_key)


settings = Settings()
