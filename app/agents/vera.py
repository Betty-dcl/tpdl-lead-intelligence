"""Vera — Verification & Quality (cross-cutting QA, the 9th agent).

Vera is not a pipeline step; she is the QA gate between the others. She reads the
scored DB and surfaces what a human must check before TPDL acts on it: signals
without a verifiable source, undated high-confidence claims, boilerplate
rationale reused across companies, and speculation/negation scored as fact.

Slash commands (read the DB; Claude interprets — every run is logged to
activity_log via BaseAgent.respond, so Vera's checks are traceable):
  - /review          → the human-review queue (auto-flagged companies, pending).
  - /audit [company] → deep QA of one company, issue by issue, with a verdict.
  - /stats           → QA health: flagged / reviewed / common reasons.
"""
from typing import Optional

from sqlalchemy import func

from app.agents.base import BaseAgent
from app.config import AgentID
from app.database import SessionLocal
from app.models import Company, Signal

VERA_ID: str = AgentID.VERA.value

# Speculation / negation markers — a signal whose text hedges like this has not
# necessarily happened; it must be verified, not scored as fact.
_SPECULATION = (
    "in talks", "considering", "reportedly", "allegedly", "rumour", "rumor",
    "may ", "might ", "could ", "would ", "plans to", "planning to",
    "expected to", "is set to", "potential", "no longer", "denied", "denies",
)


def _has_speculation(text: str | None) -> bool:
    if not text:
        return False
    low = " " + text.lower() + " "
    return any(m in low for m in _SPECULATION)


def audit_signals(signals: list[Signal], boilerplate_rationales: set[str]) -> list[str]:
    """Deterministic, traceable QA findings for one company's signals.

    `boilerplate_rationales` = why_it_matters strings that recur on 3+ companies
    (computed once by the caller). Pure function → unit-testable, no DB here.
    """
    issues: list[str] = []
    for s in signals:
        has_url = bool((s.urls or "").strip())
        conf = (s.confidence or "").lower()
        if conf == "high" and not has_url:
            issues.append(f"{s.category}: high confidence but NO verifiable source URL")
        if not has_url and not (s.sources or "").strip():
            issues.append(f"{s.category}: no source at all (unverifiable)")
        if _has_speculation(s.what_happened):
            issues.append(f"{s.category}: speculative/negated wording — verify the event happened")
        if s.why_it_matters and s.why_it_matters in boilerplate_rationales:
            issues.append(f"{s.category}: boilerplate rationale (reused on 3+ companies)")
    return issues


def _boilerplate_set(db) -> set[str]:
    rows = (db.query(Signal.why_it_matters, func.count(func.distinct(Signal.company_name)))
            .filter(Signal.why_it_matters.isnot(None))
            .group_by(Signal.why_it_matters)
            .having(func.count(func.distinct(Signal.company_name)) >= 3)
            .all())
    return {r[0] for r in rows}


class VeraAgent(BaseAgent):
    def _dispatch_command(self, user_message: str) -> Optional[dict]:
        text = user_message.strip()
        low = text.lower()

        # ── /audit [company] ─────────────────────────────────────────────
        if low.startswith("/audit") or low.startswith("/qa"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                return {
                    "augmented_message": "The user ran `/audit` with no company. Ask which company they want quality-audited.",
                    "action": "qa_audit", "task_title": "/audit (no company)",
                }
            name = parts[1].strip()
            name_low = name.lower()
            with SessionLocal() as db:
                c = db.get(Company, name)
                if c is None:
                    for row in db.query(Company).all():
                        if row.name.lower() == name_low or name_low in row.name.lower():
                            c = row
                            break
                if c is None:
                    return {
                        "augmented_message": f"The user asked to audit '{name}', not in the scored universe. Suggest checking the name.",
                        "action": "qa_audit", "task_title": f"/audit: {name} (not found)",
                    }
                signals = db.query(Signal).filter(Signal.company_name == c.name).all()
                issues = audit_signals(signals, _boilerplate_set(db))
            if c.review_flag and c.review_flag_reason:
                issues.append(f"pipeline flag: {c.review_flag_reason}")
            verdict = "NEEDS REVIEW" if issues else "CLEAR"
            issue_str = "\n".join(f"  - {i}" for i in issues) or "  (none)"
            augmented = (
                f"The user ran `/audit {c.name}`. Here is the QA data:\n\n"
                f"COMPANY: {c.name} · score {c.assessed_score} · {len(signals)} signal(s) · "
                f"confidence set: {', '.join(sorted({s.confidence or '—' for s in signals})) or '—'}\n"
                f"Automated QA findings ({len(issues)}):\n{issue_str}\n"
                f"Current review status: {c.review_status or 'not reviewed'}\n\n"
                f"As Vera, give the verdict **{verdict}** first, then explain each finding in one "
                f"line and what a human should verify (open the source URL, confirm the date). "
                f"If CLEAR, say what you checked. Reason ONLY from the data above — never invent."
            )
            return {
                "augmented_message": augmented, "action": "qa_audit",
                "task_title": f"Audit — {c.name}",
                "metadata": {"company": c.name, "verdict": verdict, "issues": len(issues)},
            }

        # ── /review — the human-review queue ─────────────────────────────
        if low == "/review" or low.startswith("/review"):
            with SessionLocal() as db:
                pending = (db.query(Company)
                           .filter(Company.review_flag.is_(True),
                                   Company.review_status.is_(None))
                           .order_by(Company.assessed_score.desc())
                           .limit(40).all())
                total_flagged = (db.query(func.count(Company.name))
                                 .filter(Company.review_flag.is_(True)).scalar() or 0)
            if not pending:
                augmented = (
                    f"The user ran `/review`. There are {total_flagged} review-flagged "
                    f"companies and NONE are still pending — all have been reviewed. As Vera, "
                    f"confirm the queue is clear and remind them new flags appear as the "
                    f"pipeline runs."
                )
                meta = {"pending": 0, "flagged": total_flagged}
            else:
                lines = "\n".join(
                    f"  - {c.name} (score {c.assessed_score}): {c.review_flag_reason or 'flagged'}"
                    for c in pending
                )
                augmented = (
                    f"The user ran `/review`. Human-review QUEUE — {len(pending)} pending of "
                    f"{total_flagged} flagged:\n\n{lines}\n\n"
                    f"As Vera, present this as the queue: group by reason, put the highest-score "
                    f"(highest-risk-if-wrong) first, and remind them each is a ~60-second check "
                    f"on the Review page (approve = safe to act, reject = don't use the signal)."
                )
                meta = {"pending": len(pending), "flagged": total_flagged}
            return {"augmented_message": augmented, "action": "qa_review",
                    "task_title": "Review queue", "metadata": meta}

        # ── /stats — QA health ───────────────────────────────────────────
        if low == "/stats" or low.startswith("/stats"):
            with SessionLocal() as db:
                flagged = (db.query(func.count(Company.name))
                           .filter(Company.review_flag.is_(True)).scalar() or 0)
                approved = (db.query(func.count(Company.name))
                            .filter(Company.review_status == "approved").scalar() or 0)
                rejected = (db.query(func.count(Company.name))
                            .filter(Company.review_status == "rejected").scalar() or 0)
                reasons = (db.query(Company.review_flag_reason, func.count(Company.name))
                           .filter(Company.review_flag.is_(True),
                                   Company.review_flag_reason.isnot(None))
                           .group_by(Company.review_flag_reason)
                           .order_by(func.count(Company.name).desc()).limit(6).all())
            reason_str = "\n".join(f"  - {r or '—'}: {n}" for r, n in reasons) or "  (none)"
            augmented = (
                f"The user ran `/stats`. QA health of the current run:\n"
                f"- Review-flagged: {flagged}\n- Reviewed → approved: {approved} · rejected: {rejected} · "
                f"pending: {max(0, flagged - approved - rejected)}\n"
                f"- Top flag reasons:\n{reason_str}\n\n"
                f"As Vera, summarise the quality state in a few tight lines and say what to "
                f"prioritise on the Review page. Reason only from these numbers."
            )
            return {"augmented_message": augmented, "action": "qa_stats",
                    "task_title": "QA stats",
                    "metadata": {"flagged": flagged, "approved": approved, "rejected": rejected}}

        return None
