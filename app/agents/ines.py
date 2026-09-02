"""Inès — Contacts & Radars (step 3 of the sales pipeline).

From Maya's shortlist, Inès pulls decision-makers (CEO/CTO/CFO + LinkedIn) via
Apollo and tags them with three radars (Lunch Campaign, Language, Premium 5).

Slash commands:
  - /contacts [company] → pull + tag decision-makers for a company (Apollo).
  - /contacts shortlist → batch hand-off: build the brief for Maya's whole ACT NOW band.
  - /radars             → Lunch Campaign (CH/Spain) & Language (ES) candidates.
  - /premium            → the Premium 5 hand-picked for Andrés (a real human).
  - /generate [company] → alias of /contacts (used by the workspace "Generate brief" button).
  - /moves [review|approved|approve <id>|dismiss <id>|connected <id>|
    followed-up <id>|followup] → executive-moves review queue + workflow state
    (chantier 4/4, 2026-09-01 recap). Inès HOSTS the queue (decision Betty,
    2026-09-01); the actual message drafting is Julie's (`/moves draft <id>`).
    State machine: new → approved → connection_sent → follow_up_sent (or
    dismissed at any point pre-send). Data comes from `pipeline/exec_moves.py`
    (Terminal-only, industry-wide discovery, NOT per-company like her other
    commands). LinkedIn sending is ALWAYS 100% human — never automated from here.

Contacts data needs APOLLO_API_KEY. Until it's set, Inès still runs the radars
on the companies' own locations (real data) and explains what she'd fetch.
"""
from typing import Optional

from sqlalchemy import func

from app.agents.base import BaseAgent
from app.config import AgentID
from app.database import SessionLocal
from app.models import Company, Contact
from app.tools import apollo, kaspr
from app.tools.radars import apply_radars, detect_country
from app.tools.scraper_brief import (
    render_batch_line,
    render_company_brief,
    render_shared_config,
)
from app.tools.segmentation import classify_function, classify_seniority, initial_crm_segment
from app.tools.shortlist import shortlist_bands

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
            # ── Batch hand-off from Maya: /contacts shortlist ────────────────
            # Instead of one company at a time, take Maya's current ACT NOW band
            # (the SAME shortlist_bands definition Maya uses) and build the
            # scraper-ready brief for each. This is the Maya → Inès pipe.
            if name.lower() in ("shortlist", "batch", "maya"):
                with SessionLocal() as db:
                    act, _monitor = shortlist_bands(db)
                if not act:
                    return {
                        "augmented_message": (
                            "The user ran `/contacts shortlist`. Maya's ACT NOW band "
                            "(in-scope, score ≥ 8) is EMPTY this run — there is nothing "
                            "above the outreach bar to pull. As Inès, say so honestly: the "
                            "MONITOR bench (5-7) is not outreach yet; don't invent targets."
                        ),
                        "action": "pulled_contacts",
                        "task_title": "Contacts batch — shortlist (empty)",
                    }
                CAP = 15
                shown = act[:CAP]
                provider = kaspr if kaspr.is_configured() else apollo
                engine = ("no contact engine connected (Mode A: brief only)"
                          if not provider.is_configured()
                          else f"{'Kaspr' if provider is kaspr else 'Apollo'} connected")
                # One deterministic brief skeleton so §3b (4 ICP functions +
                # Med-Affairs sub-batch) and §3c (tie-back) can never be dropped:
                # the shared config once, then the per-company varying part.
                lines = [render_batch_line(c) for c in shown]
                more = (f"\n(+{len(act) - CAP} more ≥8 not shown — narrow with filters)"
                        if len(act) > CAP else "")
                augmented = (
                    f"The user ran `/contacts shortlist` — the BATCH hand-off from Maya. "
                    f"Maya's ACT NOW band (in-scope, score ≥ 8) has {len(act)} companies; "
                    f"here are the top {len(shown)} by score/coverage/freshness.\n\n"
                    f"{render_shared_config()}\n\nPER-COMPANY TARGETING:\n"
                    + "\n".join(lines) + more +
                    f"\n\nEngine status: {engine}. As Inès, present this as the SCRAPER-READY "
                    f"BRIEF batch for Nathalie / Marketeering.ai — keep the 4 ICP functions, the "
                    f"Medical Affairs SEPARATE sub-batch, the Sales Nav config, the capture "
                    f"fields, and the §3c tie-back checks intact for every company. No invented "
                    f"names. Name the 3-5 companies to start with."
                )
                return {
                    "augmented_message": augmented,
                    "action": "pulled_contacts",
                    "task_title": f"Contacts batch — {len(shown)} from Maya's shortlist",
                    "metadata": {"companies": len(shown), "act_total": len(act),
                                 "provider_configured": provider.is_configured()},
                }
            c = _find_company(name)
            if c is None:
                return {
                    "augmented_message": f"The user asked for contacts at '{name}', not in the scored universe. Suggest checking the name or asking Maya for the shortlist.",
                    "action": "pulled_contacts",
                    "task_title": f"/contacts: {name} (not found)",
                }
            radar = apply_radars(None, c.location)
            # Contact provider: Kaspr is the target engine (better CH/ES coverage);
            # prefer it when its key is set, else fall back to Apollo. Both share
            # the same fetch_contacts contract, so the rest of the flow is identical.
            provider = kaspr if kaspr.is_configured() else apollo
            provider_name = "Kaspr" if provider is kaspr else "Apollo"
            # Signal-driven targeting: the lead signal decides WHICH roles matter.
            lead_signal = c.s1_category
            target_titles = provider.titles_for_signal(lead_signal)
            company_line = (
                f"COMPANY: {c.name} · {c.sector_bucket or '—'} · {c.location or 'location unknown'} · "
                f"score {c.assessed_score}\n"
                f"Lead signal: {lead_signal or 'none evidenced'} → prioritise these roles: "
                f"{', '.join(target_titles)}\n"
                f"Company-level radar: country={radar['country'] or 'other'} · "
                f"lunch_campaign={radar['lunch_campaign']} · default language={radar['language']}"
            )
            if not provider.is_configured():
                augmented = (
                    f"The user ran `/contacts {c.name}`. No contact engine is connected yet "
                    f"(neither KASPR_API_KEY nor APOLLO_API_KEY set), so I cannot pull live "
                    f"people. Instead of stopping at 'I'd pull later', hand over the "
                    f"scraper-ready brief the team can give Marketeering.ai NOW:\n\n"
                    f"{render_company_brief(c)}\n\n"
                    f"As Inès, present this brief in your own voice, keeping every part intact "
                    f"(signal-driven priority roles, the 4 ICP functions, the Medical Affairs "
                    f"SEPARATE sub-batch, the Sales Nav config, capture fields, and the §3c "
                    f"tie-back checks). Note that once Kaspr/Apollo is connected the actual "
                    f"names + LinkedIn get pulled and auto-tagged, and the Premium 5 hand-picked "
                    f"for Andrés. No invented people."
                )
            else:
                fetched = provider.fetch_contacts(c.name, target_titles)
                with SessionLocal() as db:
                    # Dedup on re-run: one row per (company, person). Skip anyone
                    # already stored for this company so /contacts is idempotent
                    # and doesn't double rows (or clobber a Premium tag) on re-pull.
                    existing = {
                        n.lower() for (n,) in db.query(Contact.full_name)
                        .filter(Contact.company_name == c.name).all()
                    }
                    added = 0
                    for p in fetched:
                        full_name = p.get("full_name", "Unknown")
                        if full_name.lower() in existing:
                            continue
                        title = p.get("title")
                        r = apply_radars(full_name, p.get("location") or c.location)
                        fn = classify_function(title)
                        seniority = classify_seniority(title)
                        db.add(Contact(
                            company_name=c.name,
                            full_name=full_name,
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
                        existing.add(full_name.lower())
                        added += 1
                    db.commit()
                augmented = (
                    f"The user ran `/contacts {c.name}`. {provider_name} returned {len(fetched)} "
                    f"decision-maker(s); stored {added} new (deduped on re-run), each tagged "
                    f"with the full 5-axis segmentation (function · seniority · geo · language · "
                    f"CRM segment).\n\n{company_line}\n\n"
                    f"As Inès, summarise who was found with their function/seniority and CRM "
                    f"segment (2 = active pursuit, 3 = nurture; segment 1 is deferred to CRM "
                    f"confirmation), their radar tags, and which to prioritise. Remind the user "
                    f"they can mark Premium 5 for Andrés."
                )
            return {
                "augmented_message": augmented,
                "action": "pulled_contacts",
                "task_title": f"Contacts — {c.name}",
                "metadata": {"company": c.name, "provider": provider_name.lower(),
                             "contacts_configured": provider.is_configured()},
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
                    matches = [c for c in db.query(Contact).all()
                               if target.lower() in c.full_name.lower()]
                    if not matches:
                        augmented = (
                            f"The user tried to mark '{target}' as Premium, but no such contact is "
                            f"stored yet (contacts come from Apollo). As Inès, explain that the "
                            f"Premium 5 hand-pick happens once contacts are pulled."
                        )
                    elif len(matches) > 1:
                        names = ", ".join(sorted(c.full_name for c in matches)[:8])
                        augmented = (
                            f"'{target}' matches {len(matches)} stored contacts ({names}). As Inès, "
                            f"ask for the FULL name — a Premium pick goes to Andrés, so never guess "
                            f"which person is meant."
                        )
                    elif matches[0].premium:
                        augmented = (
                            f"{matches[0].full_name} is ALREADY in the Premium {count}/5 (routed to "
                            f"**Andrés**). As Inès, confirm no change was made — the count stays {count}/5."
                        )
                    elif count >= 5:
                        augmented = (
                            "The Premium 5 is already full. As Inès, say one must be removed "
                            "(`/premium clear`) before adding another — only 5 go to Andrés."
                        )
                    else:
                        contact = matches[0]
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

        # ── /moves [review | approved | approve <id> | dismiss <id>] ───────
        if low.startswith("/moves"):
            from app.models import ExecutiveMove
            from app.tools.exec_titles import RETENTION_DAYS_DISMISSED

            parts = text.split(maxsplit=2)
            sub = parts[1].lower() if len(parts) > 1 else "review"

            def _move_line(m: ExecutiveMove) -> str:
                role = f", {m.role_function}" if m.role_function and m.role_function != "other" else ""
                return (f"- #{m.id} {m.person_name} → {m.new_title} @ {m.new_company} "
                        f"({m.seniority_tier}{role})")

            if sub in ("approve", "dismiss"):
                move_id_raw = parts[2].strip() if len(parts) > 2 else ""
                if not move_id_raw.isdigit():
                    return {
                        "augmented_message": f"The user ran `/moves {sub}` without a valid id. As "
                                             f"Inès, ask which move id (see `/moves review`) — never guess.",
                        "action": "exec_move_review", "task_title": f"/moves {sub} (no id)",
                    }
                move_id = int(move_id_raw)
                from app.tools.moves import approve_move, dismiss_move
                with SessionLocal() as db:
                    m, outcome = (approve_move(db, move_id) if sub == "approve"
                                 else dismiss_move(db, move_id))
                    if outcome == "not_found":
                        augmented = (f"No executive move with id {move_id}. As Inès, say it wasn't "
                                    f"found — check `/moves review` for the current queue.")
                    elif outcome == "already":
                        augmented = (f"Move #{move_id} ({m.person_name} → {m.new_title} @ "
                                    f"{m.new_company}) is already '{m.status}', not 'new'. As Inès, "
                                    f"confirm no change was made.")
                    else:
                        if sub == "approve":
                            augmented = (
                                f"Approved move #{move_id}: {m.person_name} → {m.new_title} @ "
                                f"{m.new_company}. As Inès, confirm; next step is Julie drafting an "
                                f"acknowledge-only LinkedIn message (`andres_linkedin.md` playbook), "
                                f"then a HUMAN sends the connection request — never automated."
                            )
                        else:
                            augmented = (
                                f"Dismissed move #{move_id}: {m.person_name} → {m.new_title} @ "
                                f"{m.new_company}. As Inès, confirm; this row auto-purges after "
                                f"{RETENTION_DAYS_DISMISSED} days (GDPR retention policy)."
                            )
                return {"augmented_message": augmented, "action": "exec_move_review",
                        "task_title": f"Move {sub} #{move_id}"}

            if sub in ("connected", "followed-up"):
                move_id_raw = parts[2].strip() if len(parts) > 2 else ""
                if not move_id_raw.isdigit():
                    return {
                        "augmented_message": f"The user ran `/moves {sub}` without a valid id. As "
                                             f"Inès, ask which move id — never guess.",
                        "action": "exec_move_review", "task_title": f"/moves {sub} (no id)",
                    }
                move_id = int(move_id_raw)
                from app.tools.moves import mark_connected, mark_followed_up
                with SessionLocal() as db:
                    m, outcome = (mark_connected(db, move_id) if sub == "connected"
                                 else mark_followed_up(db, move_id))
                    if outcome == "not_found":
                        augmented = (f"No executive move with id {move_id}. As Inès, say it wasn't "
                                    f"found — check `/moves review`/`/moves approved` for the queue.")
                    elif outcome == "not_approved":
                        augmented = (f"Move #{move_id} ({m.person_name}) is '{m.status}', not "
                                    f"'approved' — it must be approved first. As Inès, explain the "
                                    f"order: `/moves approve <id>` before `/moves connected <id>`.")
                    elif outcome == "not_due":
                        augmented = (f"Move #{move_id} ({m.person_name}) is '{m.status}', not "
                                    f"'connection_sent' — nothing to follow up on yet. As Inès, "
                                    f"explain the order: `/moves connected <id>` happens first.")
                    elif sub == "connected":
                        augmented = (
                            f"Marked move #{move_id} as connected: {m.person_name} → {m.new_title} @ "
                            f"{m.new_company}. Follow-up window opens {m.follow_up_date} (~4 months — "
                            f"people tend to make strategic changes ~6 months into a new role, so this "
                            f"lands just before that). As Inès, confirm; `/moves followup` will surface "
                            f"it when due."
                        )
                    else:
                        augmented = (
                            f"Marked move #{move_id} as followed up: {m.person_name} → {m.new_title} @ "
                            f"{m.new_company}. As Inès, confirm — this move's cycle is complete."
                        )
                return {"augmented_message": augmented, "action": "exec_move_review",
                        "task_title": f"Move {sub} #{move_id}"}

            # /moves followup — connected moves whose 4-month window has arrived
            if sub == "followup":
                from app.tools.moves import due_for_follow_up
                with SessionLocal() as db:
                    rows = due_for_follow_up(db)
                if rows:
                    lines = "\n".join(
                        f"- #{m.id} {m.person_name} @ {m.new_company} — connected "
                        f"{m.connection_sent_at.date() if m.connection_sent_at else '—'}, "
                        f"follow-up due {m.follow_up_date}"
                        for m in rows
                    )
                    augmented = (
                        f"The user ran `/moves followup`. {len(rows)} move(s) due for their 4-month "
                        f"follow-up:\n{lines}\n\n"
                        f"As Inès, list them and tell the user Julie can draft the follow-up message "
                        f"(`/moves draft <id>`), then a human sends it and marks it with "
                        f"`/moves followed-up <id>`."
                    )
                else:
                    augmented = ("The user ran `/moves followup`. Nothing due right now — moves "
                                "surface here 4 months after `/moves connected <id>` was run. As "
                                "Inès, say so plainly.")
                return {"augmented_message": augmented, "action": "exec_move_review",
                        "task_title": "Moves follow-up", "metadata": {"count": len(rows)}}

            # /moves approved — approved, not yet connected (ready for a human to send)
            if sub == "approved":
                with SessionLocal() as db:
                    rows = (db.query(ExecutiveMove).filter(ExecutiveMove.status == "approved")
                            .order_by(ExecutiveMove.id.desc()).limit(20).all())
                if rows:
                    lines = "\n".join(_move_line(m) for m in rows)
                    augmented = (
                        f"The user ran `/moves approved`. {len(rows)} approved move(s), ready for a "
                        f"human to send the LinkedIn connection request (never automated):\n{lines}\n\n"
                        f"As Inès, list them; remind the user the actual send is 100% manual."
                    )
                else:
                    augmented = ("The user ran `/moves approved`. Nothing approved yet — see "
                                "`/moves review` and `/moves approve <id>`. As Inès, say so plainly.")
                return {"augmented_message": augmented, "action": "exec_move_review",
                        "task_title": "Moves approved", "metadata": {"count": len(rows)}}

            # /moves [review] — the default: moves awaiting a human decision
            with SessionLocal() as db:
                rows = (db.query(ExecutiveMove).filter(ExecutiveMove.status == "new")
                        .order_by(ExecutiveMove.discovered_at.desc()).limit(20).all())
            if rows:
                lines = "\n".join(_move_line(m) for m in rows)
                augmented = (
                    f"The user ran `/moves review`. {len(rows)} executive move(s) awaiting review "
                    f"(from `pipeline/exec_moves.py`, run manually from the Terminal):\n{lines}\n\n"
                    f"As Inès, summarise who moved where, flag anything that looks thin (no date, "
                    f"vague company name — never invent detail on a candidate not shown here), and "
                    f"tell the user they can `/moves approve <id>` or `/moves dismiss <id>`."
                )
            else:
                augmented = (
                    "The user ran `/moves review`. No moves awaiting review right now — either the "
                    "weekly discovery pass hasn't been run (`python pipeline/exec_moves.py --live`, "
                    "Terminal only) or everything already got triaged. As Inès, explain this plainly, "
                    "never invent a move."
                )
            return {"augmented_message": augmented, "action": "exec_move_review",
                    "task_title": "Moves review", "metadata": {"count": len(rows)}}

        return None
