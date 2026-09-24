"""FastAPI dependency providers.

Dependencies are how route handlers receive shared resources (settings, a database session,
the current user…) without importing globals. Everything is read from ``app.state``, which
``create_app`` fills in — so tests can build an app with different settings and get fully
isolated resources.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.utils.metrics import Metrics


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_metrics(request: Request) -> Metrics:
    return request.app.state.metrics


def get_db(request: Request) -> Iterator[Session]:
    """One database session per request; always closed (and rolled back if uncommitted)."""
    session = request.app.state.db.session_factory()
    try:
        yield session
    finally:
        session.close()


AppSettings = Annotated[Settings, Depends(get_app_settings)]
AppMetrics = Annotated[Metrics, Depends(get_metrics)]
DbSession = Annotated[Session, Depends(get_db)]
