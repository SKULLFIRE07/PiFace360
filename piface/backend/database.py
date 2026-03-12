"""
PiFace Attendance System - Database Configuration

SQLAlchemy setup for SQLite with WAL mode and optimized PRAGMAs.
"""

import logging
import os
from pathlib import Path

from sqlalchemy import event, create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database path resolution
# ---------------------------------------------------------------------------
_PRODUCTION_DB_DIR = Path("/opt/piface/database")
_PRODUCTION_DB_PATH = _PRODUCTION_DB_DIR / "attendance.db"

if _PRODUCTION_DB_DIR.exists() and os.access(_PRODUCTION_DB_DIR, os.W_OK):
    DB_PATH: Path = _PRODUCTION_DB_PATH
else:
    # Fallback for development: store next to this module
    DB_PATH = Path(__file__).resolve().parent / "attendance.db"

DB_URL = f"sqlite:///{DB_PATH}"

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Apply performance and safety PRAGMAs on every new connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA wal_autocheckpoint=1000")
    cursor.close()


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------
Base = declarative_base()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
def get_db():
    """Yield a database session and ensure it is closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------
def init_db() -> None:
    """Create all tables and run a startup integrity check."""
    # Ensure the parent directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Import models so Base.metadata knows about every table
    from piface.backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified at %s", DB_PATH)

    # Startup integrity check
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA quick_check")).fetchone()
        status = result[0] if result else "unknown"
        if status == "ok":
            logger.info("Database integrity check passed.")
        else:
            logger.warning("Database integrity check returned: %s", status)
