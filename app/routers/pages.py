from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import TEMPLATES_DIR
from app.database import get_db
from app.models import Agent

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
def office(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "office.html",
        {"active_page": "office"},
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
    return templates.TemplateResponse(
        request,
        "intel.html",
        {"active_page": "intel"},
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


@router.get("/today", response_class=HTMLResponse)
def today_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "today.html",
        {"active_page": "today"},
    )


@router.get("/credits", response_class=HTMLResponse)
def credits_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "credits.html",
        {"active_page": "credits"},
    )


@router.get("/data", response_class=HTMLResponse)
def data_view(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "onedrive.html",
        {"active_page": "data"},
    )


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
