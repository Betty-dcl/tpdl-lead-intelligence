"""Step 1 — Tech scan: detect a company's public tech stack (Wappalyzer/Apify).

Per the Neotek spec (Pipeline Documentation §8), this scan produces a
`Tech Stack Summary` that is passed to the interpreter as evidence. Two
outcomes are themselves commercial signals:

  • no_tech_detected  — a completely empty scan at this revenue level means
    the company operates below its digital-maturity floor (a digital gap).
    Neotek's run: 47/476 companies (10%). Surfaced to Sonnet as evidence.
  • scan_blocked      — the site blocked the scanner, true stack unknown →
    the Intelligence Summary recommends manual verification.
    Neotek's run: 103/476 (22%).

Live scan goes through Apify (require_live money gate). Dry-run uses a
deterministic mock driven by an optional `technologies` hint on the
company identity — zero network, zero cost.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from pipeline.config import APIFY_WAPPALYZER_ACTOR, EngineConfig, require_live

logger = logging.getLogger(__name__)

# Technology-name → category. Lowercased substring match on detected tech names.
_CRM = ("salesforce", "hubspot", "microsoft dynamics", "dynamics 365", "zoho crm",
        "pipedrive", "sugarcrm", "veeva", "sap crm", "oracle crm", "netsuite")
_MARKETING_AUTOMATION = ("marketo", "pardot", "hubspot marketing", "eloqua",
                         "mailchimp", "activecampaign", "klaviyo", "braze",
                         "adobe campaign", "acoustic")
_ANALYTICS = ("google analytics", "adobe analytics", "mixpanel", "amplitude",
              "segment", "hotjar", "matomo", "piwik", "heap")
_ADVERTISING = ("google ads", "doubleclick", "facebook pixel", "meta pixel",
                "linkedin insight", "google tag manager", "the trade desk")


def _match(names: list[str], vocab: tuple[str, ...]) -> list[str]:
    low = [n.lower() for n in names]
    return sorted({raw for raw, l in zip(names, low)
                   if any(term in l for term in vocab)})


@dataclass
class TechScan:
    domain: str | None
    technologies: list[str] = field(default_factory=list)
    crm: list[str] = field(default_factory=list)
    marketing_automation: list[str] = field(default_factory=list)
    analytics: list[str] = field(default_factory=list)
    advertising: list[str] = field(default_factory=list)
    no_tech_detected: bool = False
    scan_blocked: bool = False
    domain_missing: bool = False

    def summary(self) -> str:
        """The Tech Stack Summary string (goes into the CSV + to the interpreter)."""
        if self.domain_missing:
            return "No website on record — tech stack not scanned."
        if self.scan_blocked:
            return ("Tech scan blocked by the site — stack unknown. "
                    "Manual verification recommended.")
        if self.no_tech_detected:
            return ("No CRM, marketing automation or analytics detected — a digital "
                    "gap at this revenue level (operating below its digital-maturity floor).")
        parts = []
        if self.crm:
            parts.append("CRM: " + ", ".join(self.crm))
        else:
            parts.append("No CRM detected")
        if self.marketing_automation:
            parts.append("Marketing automation: " + ", ".join(self.marketing_automation))
        if self.analytics:
            parts.append("Analytics: " + ", ".join(self.analytics))
        if self.advertising:
            parts.append("Ad tech: " + ", ".join(self.advertising))
        return " · ".join(parts)

    def is_digital_gap(self) -> bool:
        """True when the scan is evidence of a commercial digital gap (no CRM)."""
        return self.no_tech_detected or (
            not self.scan_blocked and not self.domain_missing and not self.crm)


def _classify(domain: str | None, names: list[str]) -> TechScan:
    scan = TechScan(domain=domain, technologies=sorted(set(names)))
    scan.crm = _match(names, _CRM)
    scan.marketing_automation = _match(names, _MARKETING_AUTOMATION)
    scan.analytics = _match(names, _ANALYTICS)
    scan.advertising = _match(names, _ADVERTISING)
    scan.no_tech_detected = not names
    return scan


# ─────────────────────────────────────────────────────────────────────────────
# Live scan (Apify Wappalyzer actor) — behind the money gate
# ─────────────────────────────────────────────────────────────────────────────

def live_scan(cfg: EngineConfig, domain: str) -> TechScan:
    require_live(cfg, cfg.apify_token, "Tech scan (Apify Wappalyzer)")
    import json
    import urllib.error
    import urllib.request

    url = (f"https://api.apify.com/v2/acts/{APIFY_WAPPALYZER_ACTOR}"
           f"/run-sync-get-dataset-items?token={cfg.apify_token}")
    payload = {"urls": [{"url": domain if domain.startswith("http") else f"https://{domain}"}]}
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            items = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        # 4xx/5xx from the scan ⇒ treat as blocked (stack unknown), never crash.
        logger.info("[techscan] %s blocked/failed: HTTP %s", domain, exc.code)
        return TechScan(domain=domain, scan_blocked=True)
    if not items:
        return TechScan(domain=domain, no_tech_detected=True)
    # Wappalyzer actors return a list of {technologies:[{name,...}]} per URL.
    names: list[str] = []
    first = items[0] if isinstance(items, list) else items
    for tech in first.get("technologies", []) or []:
        name = tech.get("name") if isinstance(tech, dict) else str(tech)
        if name:
            names.append(name)
    return _classify(domain, names)


# ─────────────────────────────────────────────────────────────────────────────
# Dry-run scan — deterministic, zero network
# ─────────────────────────────────────────────────────────────────────────────

def mock_scan(domain: str | None, technologies: list[str] | None = None) -> TechScan:
    """Deterministic stand-in for the Apify scan.

    - no domain            → domain_missing
    - technologies hint     → classified exactly like a live result
    - domain but no hint    → no_tech_detected (the common digital-gap case)
    """
    if not domain:
        return TechScan(domain=None, domain_missing=True)
    if technologies:
        return _classify(domain, list(technologies))
    return TechScan(domain=domain, no_tech_detected=True)


def scan(cfg: EngineConfig, domain: str | None,
         technologies_hint: list[str] | None = None) -> TechScan:
    if not domain:
        return TechScan(domain=None, domain_missing=True)
    if cfg.live:
        try:
            return live_scan(cfg, domain)
        except Exception as exc:  # EngineOffline or network: degrade, never crash
            logger.info("[techscan] %s skipped: %s", domain, exc)
            return TechScan(domain=domain, scan_blocked=True)
    return mock_scan(domain, technologies_hint)
