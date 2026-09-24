"""FastAPI dependency providers.

Dependencies are how route handlers receive shared resources (settings, a database session,
the current user…) without importing globals. Everything is read from ``app.state``, which
``create_app`` fills in — so tests can build an app with different settings and get fully
isolated resources.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.models.db_models import User
from backend.services import auth_service
from backend.utils.errors import AuthenticationError
from backend.utils.metrics import Metrics
from backend.utils.security import TokenClaims, decode_access_token


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_metrics(request: Request) -> Metrics:
    return request.app.state.metrics


def get_db(request: Request) -> Iterator[Session]:
    """One database session per request; always closed (and rolled back if uncommitted)."""
    database = request.app.state.db
    database.ensure_tables()  # no-op normally; recovers after a database outage
    session = database.session_factory()
    try:
        yield session
    finally:
        session.close()


AppSettings = Annotated[Settings, Depends(get_app_settings)]
AppMetrics = Annotated[Metrics, Depends(get_metrics)]
DbSession = Annotated[Session, Depends(get_db)]

# Adds the "Authorize" button to the Swagger UI; auto_error=False lets us return our own
# consistent 401 error body instead of FastAPI's default 403.
bearer_scheme = HTTPBearer(auto_error=False, description="Paste the access_token from /api/login")


def get_token_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: AppSettings,
    db: DbSession,
) -> TokenClaims:
    """Authentication: is the caller who they claim to be?"""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError()
    claims = decode_access_token(
        credentials.credentials, secret=settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    if auth_service.is_token_revoked(db, claims.jti):
        raise AuthenticationError(
            "This session has been logged out. Please log in again.", code="token_revoked"
        )
    return claims


def get_current_user(
    claims: Annotated[TokenClaims, Depends(get_token_claims)], db: DbSession
) -> User:
    user = db.get(User, claims.user_id)
    if user is None:
        raise AuthenticationError("This account no longer exists.", code="invalid_token")
    return user


CurrentClaims = Annotated[TokenClaims, Depends(get_token_claims)]
CurrentUser = Annotated[User, Depends(get_current_user)]
