"""Auth routes — login page (HTML), login/logout/me (JSON)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import AUTH_GATE_ENABLED, check_password, get_current_user_optional
from app.config import TEMPLATES_DIR
from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# HTML page lives at /login (under the pages router so the path stays neat).
page_router = APIRouter(tags=["auth-pages"])
api_router = APIRouter(prefix="/api", tags=["auth"])


@page_router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Render the login page with the 5 BD users as picker options."""
    users = db.query(User).order_by(User.username).all()
    me = get_current_user_optional(request, db)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "active_page": None,
            "users": users,
            "already_logged_in": me is not None,
            "hide_chrome": True,   # login is the front door — no nav/footer
        },
    )


class LoginPayload(BaseModel):
    username: str
    password: str


@api_router.post("/login")
def login(payload: LoginPayload, request: Request, db: Session = Depends(get_db)) -> dict:
    if not check_password(payload.password):
        raise HTTPException(status_code=401, detail="Wrong team password")

    user = db.query(User).filter(User.username == payload.username.strip().lower()).first()
    if user is None:
        raise HTTPException(status_code=404, detail=f"Unknown user '{payload.username}'")

    request.session["user_id"] = user.id
    logger.info("[auth] user %s logged in", user.username)
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "avatar_seed": user.avatar_seed,
        "color": user.color,
    }


@api_router.post("/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}


@api_router.get("/me")
def me(request: Request, db: Session = Depends(get_db)) -> dict:
    user = get_current_user_optional(request, db)
    if user is None:
        return {
            "authenticated": False,
            "auth_gate": AUTH_GATE_ENABLED,
        }
    return {
        "authenticated": True,
        "auth_gate": AUTH_GATE_ENABLED,
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "avatar_seed": user.avatar_seed,
        "color": user.color,
    }
