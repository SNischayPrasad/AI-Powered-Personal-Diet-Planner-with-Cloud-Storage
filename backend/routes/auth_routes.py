"""Authentication endpoints: register, login, logout."""

import logging

from fastapi import APIRouter, Depends, status

from backend.config import API_PREFIX, Settings
from backend.models.db_models import User
from backend.models.schemas import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from backend.services import auth_service
from backend.utils.dependencies import (
    AppMetrics,
    AppSettings,
    CurrentClaims,
    DbSession,
    get_current_user,
)
from backend.utils.errors import AuthenticationError
from backend.utils.rate_limiter import auth_rate_limit
from backend.utils.security import create_access_token

logger = logging.getLogger("diet_planner.auth")

router = APIRouter(prefix=API_PREFIX, tags=["Authentication"])


def _token_response(user: User, settings: Settings) -> TokenResponse:
    token = create_access_token(
        user.id,
        secret=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.access_token_expire_minutes,
    )
    return TokenResponse(
        access_token=token.token, expires_in=token.expires_in,
        user=UserPublic.model_validate(user),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account (returns a login token)",
    dependencies=[Depends(auth_rate_limit)],
    responses={409: {"description": "Email already registered"},
               429: {"description": "Too many attempts"}},
)
def register(
    payload: RegisterRequest, db: DbSession, settings: AppSettings, metrics: AppMetrics
) -> TokenResponse:
    user = auth_service.register_user(db, payload, bcrypt_rounds=settings.bcrypt_rounds)
    metrics.inc("auth_events_total", event="register")
    logger.info("New account registered", extra={"user_id": user.id})
    return _token_response(user, settings)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in with email and password",
    dependencies=[Depends(auth_rate_limit)],
    responses={401: {"description": "Incorrect email or password"},
               429: {"description": "Too many attempts"}},
)
def login(
    payload: LoginRequest, db: DbSession, settings: AppSettings, metrics: AppMetrics
) -> TokenResponse:
    try:
        user = auth_service.authenticate_user(
            db, payload.email, payload.password, bcrypt_rounds=settings.bcrypt_rounds
        )
    except AuthenticationError:
        metrics.inc("auth_events_total", event="login_failure")
        logger.warning("Failed login attempt")
        raise
    metrics.inc("auth_events_total", event="login_success")
    return _token_response(user, settings)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Log out (revokes the current token)",
    dependencies=[Depends(get_current_user)],  # the account must still exist
    responses={401: {"description": "Missing, invalid, expired or revoked token"}},
)
def logout(claims: CurrentClaims, db: DbSession, metrics: AppMetrics) -> MessageResponse:
    auth_service.revoke_token(db, claims)
    metrics.inc("auth_events_total", event="logout")
    return MessageResponse(message="You have been logged out.")
