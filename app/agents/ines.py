"""Inès — Contacts & Radars (step 3 of the sales pipeline).

From Maya's shortlist, Inès pulls decision-makers (CEO/CTO/CFO + LinkedIn) via
Apollo and tags them with three radars (Lunch Campaign, Language, Premium 5).

Slash commands:
  - /contacts [company] → pull + tag decision-makers for a company (Apollo).
  - /radars             → Lunch Campaign (CH/Spain) & Language (ES) candidates.
  - /premium            → the Premium 5 hand-picked for Andrés (a real human).
  - /generate [company] → alias of /contacts (used by the workspace "Generate brief" button).

Contacts data needs APOLLO_API_KEY. Until it's set, Inès still runs the radars
on the companies' own locations (real data) and explains what she'd fetch.
"""
from typing import Optional

from sqlalchemy import func

from app.agents.base import BaseAgent
from app.config import AgentID
from app.database import SessionLocal
from app.models import Company, Contact
from app.tools import apollo
from app.tools.radars import apply_radars, detect_country
from app.tools.segmentation import classify_function, classify_seniority, initial_crm_segment

INES_ID: str = AgentID.INES.value


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


class InesAgent(BaseAgent):
    def _dispatch_command(self, user_message: str) -> Optional[dict]:
        text = user_message.strip()
        # Workspace "Generate brief" button sends `/generate <company>` —
        # Inès's brief is the contacts + radar read for that company.
        if text.lower().startswith("/generate"):
            text = "/contacts" + text[len("/generate"):]
        low = text.lower()

        # ── /contacts [company] ──────────────────────────────────────────
        if low.startswith("/contacts"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                return {
                    "augmented_message": "The user ran `/contacts` with no company. Ask which shortlisted company they want decision-maker contacts for.",
                    "action": "pulled_contacts",
                    "task_title": "/contacts (no company)",
                }
            name = parts[1].strip()
            c = _find_company(name)
            if c is None:
                return {
                    "augmented_message": f"The user asked for contacts at '{name}', not in the scored universe. Suggest checking the name or asking Maya for the shortlist.",
                    "action": "pulled_contacts",
                    "task_title": f"/contacts: {name} (not found)",
                }
            radar = apply_radars(None, c.location)
            company_line = (
                f"COMPANY: {c.name} · {c.sector_bucket or '—'} · {c.location or 'location unknown'} · "
                f"score {c.assessed_score}\n"
                f"Company-level radar: country={radar['country'] or 'other'} · "
                f"lunch_campaign={radar['lunch_campaign']} · default language={radar['language']}"
            )
            if not apollo.is_configured():
                augmented = (
                    f"The user ran `/contacts {c.name}`. Apollo is NOT connected yet "
                    f"(APOLLO_API_KEY missing), so I cannot pull the live CEO/CTO/CFO + "
                    f"LinkedIn data.\n\n{company_line}\n\n"
                    f"As Inès, explain: once Apollo is connected I'll pull the decision-makers "
                    f"(CEO, CTO, CFO) with their LinkedIn, then auto-tag each with the radars "
                    f"(Lunch Campaign for Switzerland/Spain, Language ES for Spain or Spanish "
                    f"names) and let the user hand-pick the Premium 5 for Andrés. For now, note "
                    f"the company-level radar read above."
                )
            else:
                fetched = apollo.fetch_contacts(c.name)
                with SessionLocal() as db:
                    for p in fetched:
                        title = p.get("title")
                        r = apply_radars(p.get("full_name"), p.get("location") or c.location)
                        fn = classify_function(title)
                        seniority = classify_seniority(title)
                        db.add(Contact(
                            company_name=c.name,
                            full_name=p.get("full_name", "Unknown"),
                            title=title,
                            email=p.get("email"),
                            linkedin_url=p.get("linkedin_url"),
                            location=p.get("location") or c.location,
                            country=r["country"],
                            language=r["language"],
                            lunch_campaign=r["lunch_campaign"],
                            function=fn,
                            seniority=seniority,
                            crm_segment=initial_crm_segment(c.outreach_eligible, fn, seniority),
                        ))
                    db.commit()
                augmented = (
                    f"The user ran `/contacts {c.name}`. Pulled and tagged {len(fetched)} "
                    f"decision-maker(s) via Apollo, each with the full 5-axis segmentation "
                    f"(function · seniority · geo · language · CRM segment).\n\n{company_line}\n\n"
                    f"As Inès, summarise who was found with their function/seniority and CRM "
                    f"segment (2 = active pursuit, 3 = nurture; segment 1 is deferred to CRM "
                    f"confirmation), their radar tags, and which to prioritise. Remind the user "
                    f"they can mark Premium 5 for Andrés."
                )
            return {
                "augmented_message": augmented,
                "action": "pulled_contacts",
                "task_title": f"Contacts — {c.name}",
                "metadata": {"company": c.name, "apollo": apollo.is_configured()},
            }

        # ── /radars ──────────────────────────────────────────────────────
        if low == "/radars" or low.startswith("/radars"):
            with SessionLocal() as db:
                companies = (
                    db.query(Company)
                    .filter(Company.icp_flag.is_(False))
                    .filter(Company.location.isnot(None))
                    .all()
                )
                n_contacts = db.query(func.count(Contact.id)).scalar() or 0
            ch = [c.name for c in companies if detect_country(c.location) == "CH"]
            es = [c.name for c in companies if detect_country(c.location) == "ES"]
            augmented = (
                f"The user ran `/radars`. Radar scan across in-scope companies by location:\n\n"
                f"🍽️ Lunch Campaign — Switzerland ({len(ch)}): {', '.join(ch[:12]) or 'none'}\n"
                f"🍽️ Lunch Campaign — Spain ({len(es)}): {', '.join(es[:12]) or 'none'}\n"
                f"🗣️ Language ES candidates (Spain-based): {len(es)}\n"
                f"📇 Contacts stored so far: {n_contacts}\n\n"
                f"As Inès, summarise: these CH/Spain companies are in-person targets "
                f"(coffee/lunch, not LinkedIn); Spain-based contacts get Spanish messaging. "
                f"Note contact-level tagging fills in once Apollo is connected."
            )
            return {
                "augmented_message": augmented,
                "action": "ran_radars",
                "task_title": "Radar scan",
                "metadata": {"ch": len(ch), "es": len(es), "contacts": n_contacts},
            }

        # ── /premium [add <name> | clear] ────────────────────────────────
        if low.startswith("/premium"):
            parts = text.split(maxsplit=2)
            sub = parts[1].lower() if len(parts) > 1 else ""

            # /premium add <name> — hand-pick a contact for Andrés (cap 5)
            if sub == "add":
                if len(parts) < 3:
                    return {
                        "augmented_message": "The user ran `/premium add` with no name. Ask which contact to hand-pick for Andrés.",
                        "action": "premium_selection", "task_title": "/premium add (no name)",
                    }
                target = parts[2].strip()
                with SessionLocal() as db:
                    count = db.query(Contact).filter(Contact.premium.is_(True)).count()
                    contact = None
                    for c in db.query(Contact).all():
                        if target.lower() in c.full_name.lower():
                            contact = c
                            break
                    if contact is None:
                        augmented = (
                            f"The user tried to mark '{target}' as Premium, but no such contact is "
                            f"stored yet (contacts come from Apollo). As Inès, explain that the "
                            f"Premium 5 hand-pick happens once contacts are pulled."
                        )
                    elif count >= 5:
                        augmented = (
                            "The Premium 5 is already full. As Inès, say one must be removed "
                            "(`/premium clear`) before adding another — only 5 go to Andrés."
                        )
                    else:
                        contact.premium = True
                        contact.status = "handed_andres"
                        db.commit()
                        augmented = (
                            f"Marked {contact.full_name} ({contact.title or '—'} @ "
                            f"{contact.company_name}) as Premium {count + 1}/5 → routed to **Andrés** "
                            f"(a real human, off the automated flow). As Inès, confirm; the rest of "
                            f"the batch continues to Julie."
                        )
                return {"augmented_message": augmented, "action": "premium_selection",
                        "task_title": f"Premium add — {target[:40]}"}

            # /premium clear — reset the hand-pick
            if sub == "clear":
                with SessionLocal() as db:
                    for c in db.query(Contact).filter(Contact.premium.is_(True)).all():
                        c.premium = False
                        c.status = "new"
                    db.commit()
                return {
                    "augmented_message": "Cleared the Premium 5 selection. As Inès, confirm it's reset.",
                    "action": "premium_selection", "task_title": "Premium cleared",
                }

            # /premium — list the current hand-pick
            with SessionLocal() as db:
                prem = db.query(Contact).filter(Contact.premium.is_(True)).all()
            if prem:
                lines = "\n".join(
                    f"- {p.full_name} ({p.title or '—'}) @ {p.company_name}" for p in prem
                )
                augmented = (
                    f"The user ran `/premium`. Current Premium {len(prem)}/5 (hand-off to Andrés):\n{lines}\n\n"
                    f"As Inès, confirm these are routed to Andrés (a real human, off the automated "
                    f"flow) and the rest continue to Julie. Use `/premium add <name>` or `/premium clear`."
                )
            else:
                augmented = (
                    "The user ran `/premium`. No Premium 5 selected yet. As Inès, explain the flow: "
                    "from the full contact batch you hand-pick the 5 most interesting people with "
                    "`/premium add <name>`; they leave the automated pipeline and go to **Andrés** (a "
                    "real human) for a personal approach, while the rest continue to Julie. Hand-picking "
                    "happens once contacts are pulled from Apollo."
                )
            return {
                "augmented_message": augmented, "action": "premium_selection",
                "task_title": "Premium 5", "metadata": {"count": len(prem)},
            }

        return None
