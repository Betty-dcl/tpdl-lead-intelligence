"""Authentication helpers — shared-password login + signed session cookie.

PUBLIC MODE (default): TPDL_AUTH_GATE != "on" → no login required, every
unauthenticated request runs as a built-in 'Guest' user. Useful for the demo
link. Collaborative actions (claim, comment, etc.) still work but attributed
to Guest.

GATED MODE: TPDL_AUTH_GATE == "on" → 5 BD users login with team password.
"""
import logging
import os
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)


TEAM_PASSWORD: str = os.environ.get("TPDL_TEAM_PASSWORD", "TPDL")


def _load_session_secret() -> str:
    """Env var first; otherwise a generated secret persisted to the data dir,
    so a dev/prod restart no longer logs the whole team out."""
    env = os.environ.get("TPDL_SESSION_SECRET")
    if env:
        return env
    from pathlib import Path
    secret_file = Path(os.environ.get("DATA_DIR", "./data")) / ".session_secret"
    try:
        if secret_file.exists():
            return secret_file.read_text(encoding="utf-8").strip()
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret = "gen-" + secrets.token_hex(32)
        secret_file.write_text(secret, encoding="utf-8")
        logger.warning(
            "[auth] TPDL_SESSION_SECRET not set — generated one at %s. "
            "Set the env var explicitly in production.", secret_file
        )
        return secret
    except OSError:
        # Read-only filesystem etc. — fall back to ephemeral (sessions reset on restart)
        return "dev-" + secrets.token_hex(16)


SESSION_SECRET: str = _load_session_secret()

# Gate toggle — default OFF so the demo link works for anyone.
AUTH_GATE_ENABLED: bool = os.environ.get("TPDL_AUTH_GATE", "off").lower() == "on"

if AUTH_GATE_ENABLED and TEAM_PASSWORD == "TPDL":
    logger.warning(
        "[auth] Auth gate is ON but TPDL_TEAM_PASSWORD is still the default "
        "('TPDL'). Set a real password in .env before sharing the link."
    )

GUEST_USERNAME = "guest"


def check_password(provided: str) -> bool:
    return secrets.compare_digest((provided or "").strip(), TEAM_PASSWORD)


def _ensure_guest(db: Session) -> User:
    """Lazily seed the Guest user the first time anyone visits in public mode."""
    g = db.query(User).filter(User.username == GUEST_USERNAME).first()
    if g is None:
        g = User(
            username=GUEST_USERNAME,
            display_name="Guest",
            avatar_seed="guest-tpdl",
            color="#5c5c5c",
        )
        db.add(g)
        db.commit()
        db.refresh(g)
        logger.info("[auth] created default Guest user")
    return g


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """FastAPI dependency. Behaviour depends on AUTH_GATE_ENABLED:
      - ON  : raise 401 if no session
      - OFF : fall back to Guest user (created lazily) so writes still work
    """
    user_id = request.session.get("user_id")
    if user_id:
        user = db.get(User, user_id)
        if user is not None:
            return user
        # Stale cookie — clear it and fall through
        request.session.pop("user_id", None)

    if AUTH_GATE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not logged in",
        )

    return _ensure_guest(db)


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)
