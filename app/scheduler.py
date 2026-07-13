"""APScheduler — background jobs for TPDL AI Team.

Jobs:
  veille_Monday  — every Monday at 08:00 local time
                   Iris scrapes trends, saves to brand memory, logs activity
  veille_adhoc   — can be triggered manually via POST /api/veille/run
"""
import json
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone="Europe/Paris")


def run_veille() -> dict:
    """Iris scans the web for pharma/medtech trends and saves to memory."""
    logger.info("[scheduler] veille started at %s", datetime.now(timezone.utc).isoformat())
    result: dict = {"status": "error", "subjects": [], "ran_at": datetime.now(timezone.utc).isoformat()}

    try:
        from app.config import AgentID, settings
        from app.database import SessionLocal
        from app.models import ActivityLog, Agent
        from app.tools.memory import get_memory, save_veille_run
        from app.tools.web_search import build_search_context

        if not settings.anthropic_api_key or settings.anthropic_api_key == "not-set":
            logger.warning("[scheduler] ANTHROPIC_API_KEY not set — veille skipped")
            result["status"] = "skipped_no_key"
            return result

        search_context = build_search_context(
            subject="pharma life sciences digital innovation leadership trends",
            sector_hint="pharma medtech dental European market",
        )

        with SessionLocal() as db:
            iris = db.get(Agent, AgentID.IRIS.value)
            if not iris:
                logger.warning("[scheduler] Iris agent not found")
                result["status"] = "skipped_no_agent"
                return result

            from app.agents.base import get_anthropic_client
            mem = get_memory()
            treated = mem.get("treated_subjects", [])
            treated_str = ", ".join(treated[-10:]) if treated else "none"

            client = get_anthropic_client()
            prompt = (
                "You are Iris running your weekly veille scan. "
                "Based on the search results below, identify the TOP 5 most compelling "
                "content subjects for TPDL this week in pharma/medtech/dental.\n\n"
                f"Already covered recently (avoid): {treated_str}\n\n"
                f"SEARCH RESULTS:\n{search_context[:4000]}\n\n"
                "For each subject output EXACTLY:\n"
                "SUBJECT: [title]\n"
                "ANGLE: [1 sentence — why this matters for TPDL's C-suite audience]\n"
                "FORMAT: [LinkedIn / PDF A4 / Both]\n"
                "---"
            )
            response = client.messages.create(
                model=settings.anthropic_model,
                system=iris.system_prompt,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
            )
            iris_text = "".join(
                b.text for b in response.content if getattr(b, "type", "") == "text"
            )

            # Parse subjects from Iris output
            subjects = []
            current: dict = {}
            for line in iris_text.splitlines():
                line = line.strip()
                if line.startswith("SUBJECT:"):
                    if current.get("subject"):
                        subjects.append(current)
                    current = {"subject": line.split(":", 1)[-1].strip()}
                elif line.startswith("ANGLE:"):
                    current["angle"] = line.split(":", 1)[-1].strip()
                elif line.startswith("FORMAT:"):
                    current["format"] = line.split(":", 1)[-1].strip()
            if current.get("subject"):
                subjects.append(current)

            save_veille_run(subjects=subjects, search_context=search_context)

            db.add(ActivityLog(
                agent_id=AgentID.IRIS.value,
                action="veille_auto",
                activity_metadata=json.dumps({
                    "subjects_found": len(subjects),
                    "search_chars": len(search_context),
                }),
            ))
            db.commit()

        result.update({"status": "ok", "subjects": subjects, "count": len(subjects)})
        logger.info("[scheduler] veille complete — %d subjects found", len(subjects))

    except Exception as exc:
        logger.exception("[scheduler] veille failed: %s", exc)
        result["error"] = str(exc)

    return result


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        run_veille,
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="veille_monday",
        name="Weekly veille — Iris",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("[scheduler] started — veille every Monday 08:00 Paris time")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[scheduler] stopped")
