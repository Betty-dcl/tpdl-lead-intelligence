import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.auth import AUTH_GATE_ENABLED, SESSION_SECRET
from app.config import STATIC_DIR, TEMPLATES_DIR
from app.database import init_db
from app.routers import (
    agents, auth, briefs, chat, companies, contacts, conversations, intel,
    marketing, memory_api, onedrive, pages, performance, pipeline, realtime, today, veille,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Rebuild the normalised signals table from the Company staging columns
    from app.database import SessionLocal
    from app.tools.signals_sync import sync_signals_from_companies
    with SessionLocal() as db:
        sync_signals_from_companies(db)
        # Jobs interrupted by the previous shutdown can never finish — mark them
        from app.models import GenerationJob
        stale = (
            db.query(GenerationJob)
            .filter(GenerationJob.status.in_(("queued", "running")))
            .update({"status": "error", "error": "Interrupted by server restart"},
                    synchronize_session=False)
        )
        if stale:
            db.commit()
            logger.info("[jobs] marked %d interrupted job(s) as error", stale)
    from app.scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="TPDL — AI Team", version="2.0.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Auth gate — redirect / 401 protected paths when not logged in.
# Public  : /, /login, /marketing, /api/login, /api/me, /api/agents,
#           /api/intel/stats, /static/*, /favicon.ico, /healthz
# Protected: /intel, /api/chat/*, /api/companies/*, /api/conversations/*,
#            /api/team/*, /agent/*
# ---------------------------------------------------------------------------

PUBLIC_PREFIXES = (
    "/static", "/healthz",
    "/login", "/api/login", "/api/me", "/api/logout",
    "/api/agents", "/api/intel/stats", "/api/marketing",
)
PUBLIC_EXACT = {"/", "/marketing"}


def _is_public(path: str) -> bool:
    if path in PUBLIC_EXACT:
        return True
    if path.startswith("/favicon"):          # /favicon.ico, /favicon-32.png, …
        return True
    # Boundary match: a prefix matches only the exact path or a segment beneath
    # it, so "/api/me" no longer whitelists "/api/memory" (auth-bypass fix).
    return any(path == p or path.startswith(p + "/") for p in PUBLIC_PREFIXES)


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    # Public-demo mode (default): every path passes through.
    if not AUTH_GATE_ENABLED:
        return await call_next(request)

    path = request.url.path
    if _is_public(path):
        return await call_next(request)

    user_id = request.session.get("user_id")
    if user_id:
        return await call_next(request)

    # Not authenticated
    if path.startswith("/api/"):
        return JSONResponse({"detail": "Not logged in"}, status_code=401)
    return RedirectResponse(url=f"/login?next={path}", status_code=303)


# Session cookie — 7-day window, signed with SESSION_SECRET (env-overridable).
# IMPORTANT: SessionMiddleware must be added AFTER the @app.middleware decorator
# so it ends up OUTER in the stack (request.session populated before auth_gate runs).
from app.config import settings as _settings

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="tpdl_session",
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
    https_only=_settings.session_https_only,  # set SESSION_HTTPS_ONLY=true in prod
)


STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(pages.router)
app.include_router(auth.page_router)
app.include_router(auth.api_router)
app.include_router(chat.router)
app.include_router(agents.router)
app.include_router(conversations.router)
app.include_router(marketing.router)
app.include_router(intel.router)
app.include_router(contacts.router)
app.include_router(companies.router)
app.include_router(performance.router)
app.include_router(pipeline.router)
app.include_router(memory_api.router)
app.include_router(veille.router)
app.include_router(realtime.router)
app.include_router(onedrive.router)
app.include_router(today.router)
app.include_router(companies.team_router)
app.include_router(briefs.router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "healthy"}


# Inline SVG favicon — avoids the /favicon.ico 404 spam in dev logs.
_FAVICON_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    b'<rect width="32" height="32" rx="6" fill="#0a0a0a"/>'
    b'<text x="50%" y="58%" text-anchor="middle" '
    b'font-family="-apple-system,Inter,sans-serif" font-size="14" '
    b'font-weight="700" fill="#34D591">T</text></svg>'
)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(content=_FAVICON_SVG, media_type="image/svg+xml")


# Custom 404
_templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.exception_handler(404)
async def not_found_handler(request: Request, exc) -> Response:
    detail = getattr(exc, "detail", "Not found")
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": detail}, status_code=404)
    return _templates.TemplateResponse(
        request,
        "404.html",
        {"path": request.url.path, "active_page": None},
        status_code=404,
    )
