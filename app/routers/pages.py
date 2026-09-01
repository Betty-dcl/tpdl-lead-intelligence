from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import TEMPLATES_DIR
from app.database import get_db
from app.models import Agent
from app.routers.traceability import SHAREPOINT_FOLDER_URL

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
def office(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "office.html",
        {"active_page": "office"},
    )


@router.get("/how-it-works", response_class=HTMLResponse)
def how_it_works(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "how_it_works.html",
        {"active_page": "how"},
    )


@router.get("/marketing", response_class=HTMLResponse)
def marketing(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "marketing.html",
        {"active_page": "marketing"},
    )


@router.get("/intel", response_class=HTMLResponse)
def intel(request: Request) -> HTMLResponse:
    """Sales hub — merged 2026-08-31: one page, three tabs (Sales / Recurring /
    Runs, via ?tab=), was three separate nav entries. See /recurring and /runs
    for the redirects that keep old links working."""
    return templates.TemplateResponse(
        request,
        "intel.html",
        {"active_page": "intel", "sharepoint_url": SHAREPOINT_FOLDER_URL},
    )


@router.get("/contacts", response_class=HTMLResponse)
def contacts_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "contacts.html",
        {"active_page": "contacts"},
    )


@router.get("/performance", response_class=HTMLResponse)
def performance(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "performance.html",
        {"active_page": "performance"},
    )


@router.get("/credits", response_class=HTMLResponse)
def credits_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "credits.html",
        {"active_page": "credits"},
    )


@router.get("/review", response_class=HTMLResponse)
def review_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "review.html",
        {"active_page": "review"},
    )


@router.get("/data", response_class=HTMLResponse)
def data_view(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "onedrive.html",
        {"active_page": "data"},
    )


@router.get("/intel/company", response_class=HTMLResponse)
def company_detail(request: Request) -> HTMLResponse:
    """Full per-company detail view. The company name arrives as ?c=<name>
    (query param, so names with punctuation need no path escaping)."""
    return templates.TemplateResponse(
        request,
        "company_detail.html",
        {"active_page": "intel"},
    )


@router.get("/recurring")
def recurring_page() -> RedirectResponse:
    """Merged into /intel (Recurring tab) on 2026-08-31 — kept as a redirect so old
    links/bookmarks/memory notes pointing at /recurring keep working."""
    return RedirectResponse(url="/intel?tab=recurring", status_code=302)


@router.get("/agent/{agent_id}", response_class=HTMLResponse)
def agent_profile(
    request: Request, agent_id: str, db: Session = Depends(get_db)
) -> HTMLResponse:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return templates.TemplateResponse(
        request,
        "agent_profile.html",
        {
            "active_page": None,
            "agent_id": agent.id,
            "agent_name": agent.name,
            "agent_role": agent.role,
            "agent_color": agent.color,
            "agent_avatar_seed": agent.avatar_seed,
        },
    )
