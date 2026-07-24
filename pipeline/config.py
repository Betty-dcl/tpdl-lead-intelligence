"""Engine configuration — scoring weights from scoring_config.yaml + env keys.

Weights are NEVER hard-coded (Constitution): edit scoring_config.yaml to retune.
The `live` flag is the money gate: False (default) ⇒ zero network, zero spend.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCORING_CONFIG = PROJECT_ROOT / "scoring_config.yaml"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Two-model split (decision 2026-07-09, supersedes the Haiku/Sonnet in the
# Neotek doc). Overridable via env without code changes.
DEFAULT_EXTRACTION_MODEL = "claude-sonnet-5"
DEFAULT_INTERPRETATION_MODEL = "claude-opus-4-8"

# Apify actor for the tech-stack scan (Step 1). Adjust to the exact actor slug
# on first live run — the run-sync endpoint contract is stable regardless.
APIFY_WAPPALYZER_ACTOR = "apify~wappalyzer"


def _parse_simple_yaml(text: str) -> dict:
    """Parse the flat two-level YAML subset used by scoring_config.yaml.

    Avoids adding a pyyaml dependency for a 10-line config file.
    Handles:  `key:`, `  sub: value  # comment`, `key: value`.
    """
    result: dict = {}
    current: dict | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        m = re.match(r"^(\s*)([\w_]+):\s*(.*)$", line)
        if not m:
            continue
        indent, key, value = m.groups()
        value = value.strip()
        if indent:  # nested under the last top-level key
            if current is not None:
                current[key] = _coerce(value)
        elif value == "":
            current = {}
            result[key] = current
        else:
            result[key] = _coerce(value)
            current = None
    return result


def _coerce(value: str):
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


@dataclass
class EngineConfig:
    # ── money gate ───────────────────────────────────────────────────────
    live: bool = False                     # False ⇒ dry-run: no network, no cost

    # ── models (two-model split, never merged) ──────────────────────────
    extraction_model: str = DEFAULT_EXTRACTION_MODEL
    interpretation_model: str = DEFAULT_INTERPRETATION_MODEL

    # ── keys (read from env; empty ⇒ that engine stays offline) ─────────
    anthropic_api_key: str = ""
    serper_api_key: str = ""               # target SERP engine (≠ SerpAPI)
    serpapi_key: str = ""                  # legacy slot, kept for transition
    exa_api_key: str = ""
    perplexity_api_key: str = ""
    firecrawl_api_key: str = ""
    apify_token: str = ""
    eu_registry_enabled: bool = True     # FREE source (public registry pages via the SERP
                                         # engine we already have — no paid API). Default ON
                                         # since 2026-07-18 (decision Betty); costs 1 extra
                                         # SERP search/company. Kill switch:
                                         # EU_REGISTRY_ENABLED=0 or CLI --no-eu-registry.
    enrich_revenue: bool = False         # opt-in (--enrich-revenue): 1 Perplexity call/company
                                         # to fill an unknown revenue so the €100M ICP floor can
                                         # apply. Fail-open (any error → revenue stays unknown).
    enrich_location: bool = False        # opt-in (--enrich-location): 1 Perplexity call/company
                                         # to fill the head-office CITY when location has none.
                                         # Fail-open (any error → location stays unchanged).

    # ── scoring weights (from scoring_config.yaml) ──────────────────────
    recency: dict = field(default_factory=lambda: {
        "within_90_days": 2, "within_6_months": 1, "no_date": 0})
    corroboration: dict = field(default_factory=lambda: {
        "multiple_sources": 2, "single_verified": 1, "single_unverified": 0})
    outreach_threshold: float = 8.0

    @classmethod
    def load(cls, live: bool = False) -> "EngineConfig":
        cfg = cls(live=live)
        # .env → os.environ (idempotent, no override of real env)
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

        cfg.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        cfg.serper_api_key = os.environ.get("SERPER_API_KEY", "")
        cfg.serpapi_key = os.environ.get("SERPAPI_KEY", "")
        cfg.exa_api_key = os.environ.get("EXA_API_KEY", "")
        cfg.perplexity_api_key = os.environ.get("PERPLEXITY_API_KEY", "")
        cfg.firecrawl_api_key = os.environ.get("FIRECRAWL_API_KEY", "")
        cfg.apify_token = os.environ.get("APIFY_TOKEN", "")
        cfg.eu_registry_enabled = os.environ.get(
            "EU_REGISTRY_ENABLED", "1").lower() not in ("0", "false", "no", "off")
        cfg.extraction_model = os.environ.get("EXTRACTION_MODEL", DEFAULT_EXTRACTION_MODEL)
        cfg.interpretation_model = os.environ.get(
            "INTERPRETATION_MODEL", DEFAULT_INTERPRETATION_MODEL)

        if SCORING_CONFIG.exists():
            weights = _parse_simple_yaml(SCORING_CONFIG.read_text())
            cfg.recency = weights.get("recency", cfg.recency)
            cfg.corroboration = weights.get("corroboration", cfg.corroboration)
            cfg.outreach_threshold = float(
                weights.get("outreach_threshold", cfg.outreach_threshold))
        return cfg


class EngineOffline(RuntimeError):
    """Raised when a live capability is requested in dry-run mode or without a key."""


def require_live(cfg: EngineConfig, key: str, what: str) -> None:
    """The single money gate: every network/API call funnels through here."""
    if not cfg.live:
        raise EngineOffline(
            f"{what}: engine is in DRY-RUN mode (no cost). Pass --live to enable.")
    if not key:
        raise EngineOffline(f"{what}: missing API key in .env.")
