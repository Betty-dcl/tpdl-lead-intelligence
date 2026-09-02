"""Julie — Segmented Outreach (step 4, final, of the sales pipeline).

Julie takes Inès's contact batch and writes outreach messages segmented by the
company's sector, grounded in TPDL's brand memory and anchored on the company's
strongest evidenced signal (from Hugo's pipeline).

Slash commands:
  - /sectors            → the configured sectors and whether each angle is set.
  - /segment [sector]   → the messaging angle TPDL uses for a sector.
  - /draft [company]    → a segmented, signal-anchored outreach email.
  - /generate [company] → alias of /draft (used by the workspace "Generate brief" button).
  - /linkedin [company] → a LinkedIn message in Andrés's voice (playbook v2.1).
  - /moves draft <id>   → executive-moves chantier (4/4, 2026-09-01 recap):
    a "Job Switch / New Role" LinkedIn message for one detected move (Inès
    hosts review/approve/dismiss/connected/followup — this is Julie's only
    step on that queue). The human send stays 100% manual either way.

Sector angles are populated with TPDL's real (anonymised) positioning (see
app/tools/sectors.py); brand voice + the real company signal ground every draft.
"""
import re
from pathlib import Path
from typing import Optional

from app.agents.base import BaseAgent
from app.config import AgentID
from app.database import SessionLocal
from app.models import Company, Contact
from app.tools import sectors as sector_tool
from app.tools.memory import get_brand_dna_block, get_brand_voice_block
from app.tools.radars import detect_country

JULIE_ID: str = AgentID.JULIE.value

_LINKEDIN_PLAYBOOK = Path(__file__).parent / "playbooks" / "andres_linkedin.md"


def _linkedin_playbook() -> str:
    try:
        return _LINKEDIN_PLAYBOOK.read_text(encoding="utf-8")
    except Exception:
        return ""


def _find_company(name: str) -> Optional[Company]:
    name_low = name.strip().lower()
    if not name_low:
        return None
    with SessionLocal() as db:
        exact = db.get(Company, name)
        if exact:
            return exact
        for c in db.query(Company).all():
            if c.name.lower() == name_low or name_low in c.name.lower():
                return c
    return None


def _resolve_company_in_text(text: str) -> tuple[Optional[Company], str]:
    """Resolve a company from a /linkedin argument → (company, extra_context).

    Tries the whole string first (a clean company name or a substring of one),
    then the longest known company name that appears inside the text — so
    `/linkedin Cantabria Labs new CEO` still anchors on Cantabria and keeps
    'new CEO' as extra operator context. Returns (None, text) when nothing
    resolves, so ad-hoc free-text outreach still works."""
    c = _find_company(text)
    if c:
        return c, ""
    low = text.lower()
    best: Optional[Company] = None
    with SessionLocal() as db:
        for row in db.query(Company).all():
            nl = row.name.lower()
            if len(nl) >= 5 and nl in low and (best is None or len(row.name) > len(best.name)):
                best = row
    if best:
        extra = re.sub(re.escape(best.name), "", text, flags=re.I).strip(" ,.-—:")
        return best, extra
    return None, text


def _strongest_signal(c: Company) -> Optional[dict]:
    for i in (1, 2, 3):
        if getattr(c, f"s{i}_category"):
            return {
                "category": getattr(c, f"s{i}_category"),
                "what_happened": getattr(c, f"s{i}_what_happened"),
                "tpdl_relevance": getattr(c, f"s{i}_tpdl_relevance"),
            }
    return None


def _primary_contact(company_name: str) -> Optional[Contact]:
    """The best stored contact to address (Inès's batch): prefer active segment,
    senior, right-function — so Julie writes TO a person, not a company."""
    _rank_sen = {"c_level": 0, "vp": 1, "director": 2, "other": 3}
    with SessionLocal() as db:
        contacts = (db.query(Contact)
                    .filter(Contact.company_name == company_name,
                            Contact.premium.is_(False))  # Premium 5 go to Andrés
                    .all())
    if not contacts:
        return None
    return sorted(contacts, key=lambda c: (
        0 if c.crm_segment == 2 else 1,
        _rank_sen.get(c.seniority or "other", 3),
    ))[0]


class JulieAgent(BaseAgent):
    def _dispatch_command(self, user_message: str) -> Optional[dict]:
        text = user_message.strip()
        # Workspace "Generate brief" button sends `/generate <company>` —
        # Julie's brief is the signal-anchored outreach draft.
        if text.lower().startswith("/generate"):
            text = "/draft" + text[len("/generate"):]
        low = text.lower()

        # ── /sectors ─────────────────────────────────────────────────────
        if low == "/sectors" or low.startswith("/sectors"):
            rows = sector_tool.list_sectors()
            lines = "\n".join(
                f"  - {name}: {'✅ angle defined' if done else '⏳ placeholder (to fill)'}"
                for name, done in rows
            )
            augmented = (
                f"The user ran `/sectors`. Configured sectors for segmentation:\n{lines}\n\n"
                f"As Julie, explain that each sector drives a tailored message angle, and that "
                f"the ⏳ ones await TPDL's positioning content. Brand voice + the company's real "
                f"signal already ground every draft today."
            )
            return {
                "augmented_message": augmented,
                "action": "listed_sectors",
                "task_title": "Sectors",
            }

        # ── /segment [sector] ────────────────────────────────────────────
        if low.startswith("/segment"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                return {
                    "augmented_message": "The user ran `/segment` with no sector. Ask which sector (pharma, dental, medtech, diagnostics, dermatology, surgery, healthcare).",
                    "action": "showed_segment",
                    "task_title": "/segment (no sector)",
                }
            sector = parts[1].strip()
            cfg = sector_tool.get_sector_angle(sector)
            defined = sector_tool.is_defined(sector)
            augmented = (
                f"The user ran `/segment {sector}`. Current angle: {cfg['angle']}\n"
                f"Proof points: {', '.join(cfg['proof_points']) or 'none yet'}\n\n"
                + ("As Julie, summarise how you'd pitch this sector." if defined else
                   "As Julie, explain this sector's angle is still a placeholder and ask TPDL "
                   "for its positioning (who we've helped, what outcome, what proof) so you can "
                   "lock the segment.")
            )
            return {
                "augmented_message": augmented,
                "action": "showed_segment",
                "task_title": f"Segment — {sector}",
                "metadata": {"sector": sector, "defined": defined},
            }

        # ── /linkedin [contact + trigger] ────────────────────────────────
        if low.startswith("/linkedin"):
            parts = text.split(maxsplit=1)
            operator_input = parts[1].strip() if len(parts) > 1 else ""
            playbook = _linkedin_playbook()
            if not playbook:
                return {
                    "augmented_message": "The user ran `/linkedin` but the Andres outreach playbook could not be loaded. As Julie, say the playbook file is missing.",
                    "action": "drafted_linkedin", "task_title": "/linkedin (no playbook)",
                }
            if not operator_input:
                return {
                    "augmented_message": (
                        "The user ran `/linkedin` with no details. As Julie (ghostwriting for "
                        "Andres), ask for the contact (name, title, company, location) AND the "
                        "trigger/campaign type before drafting — per the playbook's mandatory checks."
                    ),
                    "action": "drafted_linkedin", "task_title": "/linkedin (need details)",
                }

            # Company-aware: if the argument resolves to a scored company, the trigger
            # comes from its real signal + intelligence summary and the recipient from
            # Inès's stored contact — no need to make the operator hand-type any of it
            # (LinkedIn is TPDL's primary channel). Free-text ad-hoc outreach still works.
            company, extra = _resolve_company_in_text(operator_input)
            if company is not None:
                sig = _strongest_signal(company)
                sig_str = (f"{sig['category']} — {sig['what_happened']} "
                           f"(TPDL relevance: {sig['tpdl_relevance']})"
                           if sig else "no evidenced signal — keep it light, curiosity-led")
                contact = _primary_contact(company.name)
                contact_line = (
                    f"{contact.full_name} · {contact.title or '—'} · seniority "
                    f"{contact.seniority or '—'} · language {contact.language or 'en'}"
                    if contact else
                    "no contact pulled yet (Apollo not connected) — address the likely "
                    "decision-maker for this signal generically"
                )
                country = detect_country(company.location)
                isum = (company.intelligence_summary or "").strip() or "(no intelligence summary stored)"
                extra_line = f"\nExtra operator context: {extra}" if extra else ""
                augmented = (
                    f"Draft a LinkedIn message strictly following the Andres Burdett outreach "
                    f"system prompt below. This is anchored on a REAL scored company, so the "
                    f"trigger comes from its evidenced signal — do NOT ask the operator for one.\n\n"
                    f"COMPANY: {company.name} · {company.sector_bucket or '—'} · "
                    f"{company.location or '—'}{f' · country={country}' if country else ''}\n"
                    f"CONTACT: {contact_line}\n"
                    f"TRIGGER (Hugo's strongest signal): {sig_str}\n"
                    f"INTELLIGENCE SUMMARY (Hugo's 3-phrase read — anchor on this):\n{isum}"
                    f"{extra_line}\n\n"
                    f"Apply every playbook rule: Andres's voice (no dashes anywhere, ≤90 words, "
                    f"peer-to-peer), the location rules (Spain→Spanish + in-person lunch/coffee; "
                    f"Switzerland→English + in-person; else standard LinkedIn), trigger framing from "
                    f"the signal above, the expertise-anchor close, the two-line sign-off, and the "
                    f"exact OUTPUT FORMAT. Still run the scope check: if the company looks out of "
                    f"scope (CDMO/manufacturer/wrong division) flag it. Never invent a client or result.\n\n"
                    f"{get_brand_dna_block()}\n\n=== PLAYBOOK ===\n{playbook}"
                )
                return {
                    "augmented_message": augmented,
                    "action": "drafted_linkedin",
                    "task_title": f"LinkedIn — {company.name}",
                    "metadata": {"channel": "linkedin", "company": company.name,
                                 "recipient": contact.full_name if contact else None},
                }

            augmented = (
                f"Draft a LinkedIn message strictly following the Andres Burdett outreach system "
                f"prompt below. Apply every rule: his voice (no dashes anywhere, ≤90 words, peer-to-"
                f"peer), the location rules (Spain→Spanish + in-person; Switzerland→English + in-"
                f"person; else standard), the right trigger framing, the expertise anchor close, the "
                f"two-line sign-off, and the exact OUTPUT FORMAT. Run the mandatory checks: if the "
                f"trigger or any required detail is missing or the contact looks out of scope "
                f"(CDMO/manufacturer/wrong division), ASK before drafting rather than assuming.\n\n"
                f"OPERATOR INPUT (contact + trigger): {operator_input}\n\n"
                f"{get_brand_dna_block()}\n\n"
                f"=== PLAYBOOK ===\n{playbook}"
            )
            return {
                "augmented_message": augmented,
                "action": "drafted_linkedin",
                "task_title": f"LinkedIn — {operator_input[:50]}",
                "metadata": {"channel": "linkedin"},
            }

        # ── /moves draft <id> ────────────────────────────────────────────
        # Executive-moves chantier (4/4, 2026-09-01 recap): the ONLY step
        # Julie owns on this queue — Inès hosts review/approve/dismiss/
        # connected/followup (app/agents/ines.py). This just drafts the text;
        # the LinkedIn send stays 100% human, and Inès's `/moves connected`
        # is what actually advances the workflow state.
        if low.startswith("/moves"):
            parts = text.split(maxsplit=2)
            sub = parts[1].lower() if len(parts) > 1 else ""
            if sub != "draft":
                return {
                    "augmented_message": (
                        f"The user ran `/moves {sub}`. As Julie, explain that she only handles "
                        f"`/moves draft <id>` (writing the message) — review/approve/dismiss/"
                        f"connected/followup live with Inès."
                    ),
                    "action": "drafted_move", "task_title": f"/moves {sub} (wrong agent)",
                }
            move_id_raw = parts[2].strip() if len(parts) > 2 else ""
            if not move_id_raw.isdigit():
                return {
                    "augmented_message": "The user ran `/moves draft` without a valid id. As "
                                         "Julie, ask which move id (see Inès's `/moves review` "
                                         "or `/moves approved`) — never guess.",
                    "action": "drafted_move", "task_title": "/moves draft (no id)",
                }
            move_id = int(move_id_raw)
            from app.models import ExecutiveMove
            with SessionLocal() as db:
                m = db.get(ExecutiveMove, move_id)
            if m is None:
                return {
                    "augmented_message": f"No executive move with id {move_id}. As Julie, say it "
                                         f"wasn't found — check with Inès's `/moves review`.",
                    "action": "drafted_move", "task_title": f"/moves draft #{move_id} (not found)",
                }
            playbook = _linkedin_playbook()
            if not playbook:
                return {
                    "augmented_message": "The user ran `/moves draft` but the Andres outreach "
                                         "playbook could not be loaded. As Julie, say the "
                                         "playbook file is missing.",
                    "action": "drafted_move", "task_title": "/moves draft (no playbook)",
                }
            country = detect_country(m.location)
            prev_line = (f"{m.previous_title or 'a previous role'} at {m.previous_company}"
                        if m.previous_company else "no previous role stated in the source")
            stage_note = ("" if m.status == "approved" else
                          f" (note: this move is still '{m.status}', not yet approved by Inès — "
                          f"draft it anyway if asked, but flag that it needs `/moves approve "
                          f"{move_id}` before a human sends it)")
            augmented = (
                f"Draft a LinkedIn message strictly following the Andrés Burdett outreach system "
                f"prompt below, using the 'Job Switch / New Role (External Move)' trigger type "
                f"(see TRIGGER TYPES AND FRAMING + examples #4/#5: congratulate on the new role, "
                f"connect their new context to a relevant organisational challenge, land on the "
                f"expertise anchor). This is a REAL detected move{stage_note} — every fact below is "
                f"verbatim-sourced; do NOT invent anything beyond it.\n\n"
                f"PERSON: {m.person_name}\n"
                f"NEW ROLE: {m.new_title} at {m.new_company}"
                f"{f' ({m.location})' if m.location else ''}\n"
                f"PREVIOUSLY: {prev_line}\n"
                f"SENIORITY TIER: {m.seniority_tier}\n"
                + (f"LOCATION RULE: country={country} (Spain→Spanish+in-person; "
                   f"Switzerland→English+in-person; else standard)\n" if country else "")
                + f"SOURCE QUOTE (verbatim, grounding only — never quote it back verbatim): "
                  f"{m.quote}\n\n"
                f"Apply every playbook rule: Andrés's voice (no dashes anywhere, ≤90 words, "
                f"peer-to-peer), the location rules above, the expertise-anchor close, the "
                f"two-line sign-off, and the exact OUTPUT FORMAT. Never invent a client or "
                f"result.\n\n"
                f"{get_brand_dna_block()}\n\n=== PLAYBOOK ===\n{playbook}"
            )
            return {
                "augmented_message": augmented,
                "action": "drafted_move",
                "task_title": f"Move draft — {m.person_name}",
                "metadata": {"channel": "linkedin", "move_id": move_id,
                             "person": m.person_name, "company": m.new_company},
            }

        # ── /draft [company] ─────────────────────────────────────────────
        if low.startswith("/draft"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                return {
                    "augmented_message": "The user ran `/draft` with no company. Ask which company (from Inès's batch) to draft outreach for.",
                    "action": "drafted_outreach",
                    "task_title": "/draft (no company)",
                }
            name = parts[1].strip()
            c = _find_company(name)
            if c is None:
                return {
                    "augmented_message": f"The user asked to draft for '{name}', not in the universe. Suggest checking the name or the shortlist.",
                    "action": "drafted_outreach",
                    "task_title": f"/draft: {name} (not found)",
                }
            sig = _strongest_signal(c)
            cfg = sector_tool.get_sector_angle(c.sector_bucket)
            sig_str = (
                f"{sig['category']} — {sig['what_happened']} (TPDL relevance: {sig['tpdl_relevance']})"
                if sig else "no evidenced signal — keep it light and curiosity-led"
            )
            # #17 — address Inès's actual contact, not just the company.
            contact = _primary_contact(c.name)
            if contact:
                recipient_line = (
                    f"RECIPIENT: {contact.full_name} · {contact.title or '—'} · "
                    f"function={contact.function or '—'} · seniority={contact.seniority or '—'} · "
                    f"language={contact.language or 'en'} · CRM segment {contact.crm_segment or '—'}"
                )
                lang_note = ("Write the message in SPANISH (recipient language=es)."
                             if contact.language == "es" else
                             "Write in English.")
            else:
                recipient_line = ("RECIPIENT: no contact pulled yet (Apollo not connected) — "
                                  "address the likely decision-maker for this signal generically.")
                lang_note = "Write in English."
            isum = (c.intelligence_summary or "").strip() or "(no intelligence summary stored)"
            augmented = (
                f"The user ran `/draft {c.name}`. Write ONE outreach message.\n\n"
                f"COMPANY: {c.name} · sector: {c.sector_bucket or '—'} · {c.location or '—'} · "
                f"score {c.assessed_score}\n"
                f"{recipient_line}\n"
                f"STRONGEST SIGNAL: {sig_str}\n"
                f"INTELLIGENCE SUMMARY (Hugo's 3-phrase read — anchor the message on this, per the "
                f"constitution: situation / signal status / TPDL timing):\n{isum}\n"
                f"SECTOR ANGLE ({c.sector_bucket or 'n/a'}): {cfg['angle']}\n\n"
                f"{get_brand_dna_block()}\n\n"
                f"{get_brand_voice_block()}\n\n"
                f"OUTREACH PHILOSOPHY (non-negotiable — TPDL's hard-won lesson): direct cold "
                f"pitching is DEAD. Do NOT write a salesy pitch. Write a short, human, peer-to-"
                f"peer note (≤90 words) that: opens on the specific signal as a genuine "
                f"observation (not flattery), shows you understand the pressure it creates, and "
                f"offers a relevant perspective — NOT a demo, NOT a hard CTA. The goal is a "
                f"conversation, not a sale. If a close is needed, make it soft and optional "
                f"('happy to share what we've seen others do, no agenda'). Personalise to the "
                f"recipient's role. {lang_note} Ground every claim in a REAL Brand DNA case; if "
                f"clients/projects are still empty, keep it experience-led and never invent a "
                f"client or result. Output: a subject line (only if it's an email) + the body."
            )
            return {
                "augmented_message": augmented,
                "action": "drafted_outreach",
                "task_title": f"Outreach draft — {c.name}",
                "metadata": {"company": c.name, "sector": c.sector_bucket,
                             "sector_defined": sector_tool.is_defined(c.sector_bucket),
                             "recipient": contact.full_name if contact else None},
            }

        return None
