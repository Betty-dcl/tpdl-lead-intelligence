import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_dir() -> None:
    if settings.database_url.startswith("sqlite:///"):
        db_path = Path(settings.database_url.replace("sqlite:///", "", 1))
        db_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# Additive columns added after the initial schema shipped. `create_all` never
# ALTERs existing tables and there's no Alembic, so we add missing columns by hand.
# Additive + nullable only — safe and idempotent. SQLite-only (prod Postgres is
# migrated separately). Keep this list append-only.
_ADDITIVE_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "contacts": [
        ("function", "VARCHAR(16)"),      # Inès people-segmentation
        ("seniority", "VARCHAR(16)"),
        ("crm_segment", "INTEGER"),
    ],
    "companies": [
        ("review_status", "VARCHAR(16)"),  # Vera human-review queue
        ("reviewed_at", "DATETIME"),
        ("reviewed_note", "TEXT"),
        ("icp_flag_reason", "TEXT"),        # mega-cap ceiling + other ICP exclusions
    ],
}


def _run_lightweight_migrations() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        for table, columns in _ADDITIVE_COLUMNS.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if not existing:
                continue  # table not created yet — create_all handles it
            for name, ddl in columns:
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                    logger.info("[migrate] added column %s.%s", table, name)


def init_db() -> None:
    from app import models  # noqa: F401  — register models on Base.metadata

    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()
    logger.info("Database initialised at %s", settings.database_url)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
