"""Cloud database service.

The application talks to its database through SQLAlchemy, so the *same* code works with:

* SQLite      — a single local file, perfect for development and the "local cloud simulation";
* PostgreSQL  — a managed cloud database such as Supabase, Neon, Render or AWS RDS.

Switching between them is purely configuration: change `DATABASE_URL`. That is the cloud idea
of a *managed database* — the provider runs, patches, backs up and scales the server while the
application only needs a connection string.
"""

import logging
import re
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger("diet_planner.database")

_SQLITE_PREFIX = "sqlite:///"
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[/\\]")


class Base(DeclarativeBase):
    """Base class for every ORM model (database table)."""


def resolve_sqlite_url(url: str, base_dir: Path) -> str:
    """Turn a relative SQLite path (``sqlite:///./data/app.db``) into an absolute one rooted
    at ``base_dir``. In-memory, absolute and non-SQLite URLs are returned unchanged."""
    if not url.startswith(_SQLITE_PREFIX):
        return url
    path = url[len(_SQLITE_PREFIX):]
    if path in ("", ":memory:") or path.startswith("/") or _WINDOWS_DRIVE.match(path):
        return url
    return _SQLITE_PREFIX + (base_dir / path).resolve().as_posix()


class DatabaseService:
    """Owns the connection pool (engine) and hands out sessions (units of work)."""

    def __init__(self, database_url: str, *, base_dir: Path, echo: bool = False) -> None:
        self.url = resolve_sqlite_url(database_url, base_dir)
        url = make_url(self.url)
        self.is_sqlite = url.get_backend_name() == "sqlite"
        self.provider_name = url.get_backend_name()
        self._sqlite_file = Path(url.database) if self.is_sqlite and url.database else None

        engine_options: dict = {"echo": echo, "pool_pre_ping": True}
        if self.is_sqlite:
            # FastAPI serves requests from a thread pool; SQLite must allow that.
            engine_options["connect_args"] = {"check_same_thread": False}
        self.engine = create_engine(self.url, **engine_options)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )

    def create_tables(self) -> None:
        """Create any missing tables. (A production system would use migrations — Alembic.)"""
        if self._sqlite_file is not None and str(self._sqlite_file) != ":memory:":
            self._sqlite_file.parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(self.engine)

    def health_check(self) -> bool:
        """Readiness probe: can we run a trivial query right now?"""
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as exc:
            logger.warning("Database health check failed: %s", exc.__class__.__name__)
            return False

    def dispose(self) -> None:
        """Close pooled connections (called on application shutdown)."""
        self.engine.dispose()
