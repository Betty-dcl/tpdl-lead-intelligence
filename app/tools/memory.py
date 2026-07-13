"""Brand memory — persistent store for TPDL editorial context.

Now DB-backed (single-row `brand_memory` table, JSON document): SQLite
serialises writes, so two simultaneous generations can no longer clobber
each other — which was the risk with the old data/brand_memory.json file.

On first run, an existing brand_memory.json is migrated automatically.

Public API (unchanged):
  get_memory() / get_brand_voice_block() / record_subject()
  record_feedback() / save_veille_run() / update_brand_voice()
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MEMORY: dict = {
    "brand_voice": {
        "tone": "Analytical, direct, data-driven. No corporate jargon. UK English.",
        "audience": "VP and C-suite in European pharma, medtech, dental companies.",
        "avoid": ["AI hype", "buzzwords", "generic advice", "passive voice"],
        "structure": "Strong hook → concrete data point → TPDL angle → clear CTA.",
        "examples": [],
    },
    # Brand DNA — the firm's real story, used by Julie (outreach) and Marc
    # (content) to ground every message. TPDL fills these in (the "content I'll
    # give you later"); empty fields render as [TO FILL] so nothing is invented.
    "company": {
        "name": "The Pharma Data Lab (TPDL)",
        "history": "",      # the firm's story / positioning
        "clients": [],      # real (or anonymised) clients
        "projects": [],     # past projects + outcomes
    },
    "treated_subjects": [],
    "feedbacks": [],
    "top_performers": [],
    "veille_runs": [],
    "last_updated": None,
}


def _legacy_json_path() -> Path:
    from app.config import settings
    return Path(settings.data_dir) / "brand_memory.json"


def _load() -> dict:
    """Load the memory document from DB, migrating the legacy JSON file once."""
    from app.database import SessionLocal
    from app.models import BrandMemory

    with SessionLocal() as db:
        row = db.get(BrandMemory, 1)
        if row is not None:
            try:
                return json.loads(row.document)
            except Exception as exc:
                logger.warning("[memory] corrupt DB document, using defaults: %s", exc)
                return json.loads(json.dumps(DEFAULT_MEMORY))

        # First run — migrate legacy JSON file if present
        data = None
        legacy = _legacy_json_path()
        if legacy.exists():
            try:
                data = json.loads(legacy.read_text(encoding="utf-8"))
                logger.info("[memory] migrated legacy brand_memory.json into DB")
            except Exception as exc:
                logger.warning("[memory] legacy file unreadable, using defaults: %s", exc)
        if data is None:
            data = json.loads(json.dumps(DEFAULT_MEMORY))

        db.add(BrandMemory(id=1, document=json.dumps(data, ensure_ascii=False)))
        db.commit()
        return data


def _save(data: dict) -> None:
    from app.database import SessionLocal
    from app.models import BrandMemory

    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(data, ensure_ascii=False)

    with SessionLocal() as db:
        row = db.get(BrandMemory, 1)
        if row is None:
            db.add(BrandMemory(id=1, document=payload))
        else:
            row.document = payload
        db.commit()


# ── Public API ────────────────────────────────────────────────────────────────

def get_memory() -> dict:
    return _load()


def get_brand_voice_block() -> str:
    """Return a formatted string to inject into Marc's prompt."""
    mem = _load()
    bv = mem.get("brand_voice", {})
    treated = mem.get("treated_subjects", [])

    lines = [
        "=== TPDL BRAND MEMORY ===",
        f"Tone: {bv.get('tone', '')}",
        f"Audience: {bv.get('audience', '')}",
        f"Avoid: {', '.join(bv.get('avoid', []))}",
        f"Structure: {bv.get('structure', '')}",
    ]
    if bv.get("examples"):
        lines.append("Good examples from past content:")
        for ex in bv["examples"][-3:]:  # last 3 examples
            lines.append(f"  - {ex}")
    if treated:
        recent = treated[-10:]
        lines.append(f"Already covered (avoid repeating): {', '.join(recent)}")
    return "\n".join(lines)


def record_subject(subject: str, formats: list[str]) -> None:
    mem = _load()
    mem.setdefault("treated_subjects", []).append(subject)
    # Keep last 50
    mem["treated_subjects"] = mem["treated_subjects"][-50:]
    _save(mem)


def record_feedback(subject: str, format_id: str, decision: str, content_preview: str = "") -> None:
    """Record approve/reject decision to calibrate future generation."""
    mem = _load()
    entry = {
        "subject": subject,
        "format": format_id,
        "decision": decision,  # "approved" | "rejected"
        "preview": content_preview[:200],
        "date": datetime.now(timezone.utc).isoformat()[:10],
    }
    mem.setdefault("feedbacks", []).append(entry)
    mem["feedbacks"] = mem["feedbacks"][-100:]  # keep last 100

    if decision == "approved" and content_preview:
        mem.setdefault("top_performers", []).append({
            "subject": subject,
            "format": format_id,
            "preview": content_preview[:300],
        })
        mem["top_performers"] = mem["top_performers"][-20:]

    _save(mem)


def save_veille_run(subjects: list[dict], search_context: str) -> None:
    """Store Iris's latest veille results."""
    mem = _load()
    run = {
        "date": datetime.now(timezone.utc).isoformat(),
        "subjects": subjects,
        "search_context_length": len(search_context),
    }
    mem.setdefault("veille_runs", []).insert(0, run)
    mem["veille_runs"] = mem["veille_runs"][:10]  # keep last 10 runs
    _save(mem)


def update_brand_voice(patch: dict) -> dict:
    mem = _load()
    mem.setdefault("brand_voice", {}).update(patch)
    _save(mem)
    return mem["brand_voice"]


def get_brand_dna_block() -> str:
    """The firm's real story — injected into Julie's and Marc's prompts so every
    message is grounded in TPDL's history, clients and projects (never invented)."""
    co = _load().get("company", {})
    clients = co.get("clients") or []
    projects = co.get("projects") or []
    return "\n".join([
        "=== TPDL BRAND DNA (ground every message in this — never invent) ===",
        f"Company: {co.get('name', 'The Pharma Data Lab (TPDL)')}",
        f"History: {co.get('history') or '[TO FILL — the firm story]'}",
        f"Clients: {', '.join(clients) if clients else '[TO FILL — real/anonymised clients]'}",
        f"Projects: {', '.join(projects) if projects else '[TO FILL — past projects + outcomes]'}",
    ])


def update_company_dna(patch: dict) -> dict:
    mem = _load()
    mem.setdefault("company", {}).update(patch)
    _save(mem)
    return mem["company"]
