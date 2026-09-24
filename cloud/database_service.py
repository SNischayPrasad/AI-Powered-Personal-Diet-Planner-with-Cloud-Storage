"""Cloud database service.

The application talks to its database through SQLAlchemy, so the *same* code works with:

* SQLite      — a single local file, perfect for development and the "local cloud simulation";
* PostgreSQL  — a managed cloud database such as Supabase, Neon, Render or AWS RDS.

Switching between them is purely configuration: change `DATABASE_URL`. That is the cloud idea
of a *managed database* — the provider runs, patches, backs up and scales the server while the
application only needs a connection string.

Resilience: if the database is unreachable when the app starts, the API still starts, reports
itself as *not ready* on ``/api/health/ready`` and answers data requests with HTTP 503. It
creates its tables and recovers automatically once the database is reachable again.
"""

import logging
import re
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger("diet_planner.database")

_SQLITE_PREFIX = "sqlite:///"
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[/\\]")
POSTGRES_CONNECT_TIMEOUT_SECONDS = 10


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


def normalize_database_url(url: str) -> str:
    """Cloud providers hand out ``postgres://`` or ``postgresql://`` URLs. SQLAlchemy 2 rejects
    the first and would pick a driver implicitly for the second, so both are pinned to the
    installed psycopg2 driver. URLs that already name a driver are left alone."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
    # SQLite ignores FOREIGN KEY / ON DELETE CASCADE unless asked; PostgreSQL always enforces
    # them. Turning them on keeps local behaviour identical to the cloud database.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class DatabaseService:
    """Owns the connection pool (engine) and hands out sessions (units of work)."""

    def __init__(
        self,
        database_url: str,
        *,
        base_dir: Path,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 5,
    ) -> None:
        self.url = normalize_database_url(resolve_sqlite_url(database_url, base_dir))
        url = make_url(self.url)
        self.provider_name = url.get_backend_name()
        self.is_sqlite = self.provider_name == "sqlite"
        self._sqlite_file = Path(url.database) if self.is_sqlite and url.database else None
        self.tables_ready = False

        engine_options: dict = {"echo": echo, "pool_pre_ping": True}
        if self.is_sqlite:
            # FastAPI serves requests from a thread pool; SQLite must allow that.
            engine_options["connect_args"] = {"check_same_thread": False}
        else:
            # A bounded pool: at most pool_size + max_overflow connections per instance.
            # Managed databases cap total connections, so this matters when the app scales out.
            engine_options.update(
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_recycle=300,  # drop connections before cloud load balancers idle them out
                connect_args={"connect_timeout": POSTGRES_CONNECT_TIMEOUT_SECONDS},
            )
        self.engine = create_engine(self.url, **engine_options)
        if self.is_sqlite:
            event.listen(self.engine, "connect", _enable_sqlite_foreign_keys)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )

    def create_tables(self) -> None:
        """Create any missing tables. (A production system would use migrations — Alembic.)
        Raises SQLAlchemyError if the database is unreachable."""
        if self._sqlite_file is not None and str(self._sqlite_file) != ":memory:":
            try:
                self._sqlite_file.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:  # SQLAlchemy reports the resulting connection error
                logger.error("Cannot create the database directory: %s", exc)
        Base.metadata.create_all(self.engine)
        self.tables_ready = True

    def ensure_tables(self) -> None:
        """Cheap no-op once tables exist; otherwise try again (used after an outage)."""
        if not self.tables_ready:
            self.create_tables()

    def health_check(self) -> bool:
        """Readiness probe: can we reach the database (and are the tables in place)?"""
        try:
            self.ensure_tables()
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as exc:
            logger.warning("Database health check failed: %s", exc.__class__.__name__)
            return False

    def dispose(self) -> None:
        """Close pooled connections (called on application shutdown)."""
        self.engine.dispose()
