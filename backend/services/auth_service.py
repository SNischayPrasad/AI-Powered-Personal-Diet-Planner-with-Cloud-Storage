"""Registration, login and logout logic."""

from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.db_models import RevokedToken, User
from backend.models.schemas import RegisterRequest
from backend.utils.errors import AuthenticationError, ConflictError
from backend.utils.security import TokenClaims, hash_password, verify_password

INVALID_CREDENTIALS = "Incorrect email or password."


@lru_cache(maxsize=4)
def _dummy_hash(rounds: int) -> str:
    return hash_password("timing-equaliser-not-a-real-password-1", rounds=rounds)


def register_user(db: Session, data: RegisterRequest, *, bcrypt_rounds: int) -> User:
    duplicate = ConflictError(
        "An account with this email already exists.", code="email_already_registered"
    )
    if db.scalar(select(User.id).where(User.email == data.email)) is not None:
        raise duplicate

    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password, rounds=bcrypt_rounds),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two sign-ups with the same email at the same moment
        db.rollback()
        raise duplicate from None
    return user


def authenticate_user(db: Session, email: str, password: str, *, bcrypt_rounds: int) -> User:
    """Return the user for valid credentials. The error message is identical for an unknown
    email and a wrong password, and both paths run bcrypt — so neither the response nor its
    timing reveals which emails are registered."""
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(password, _dummy_hash(bcrypt_rounds))
        raise AuthenticationError(INVALID_CREDENTIALS, code="invalid_credentials")
    if not verify_password(password, user.password_hash):
        raise AuthenticationError(INVALID_CREDENTIALS, code="invalid_credentials")
    return user


def revoke_token(db: Session, claims: TokenClaims) -> None:
    """Server-side logout: remember the token ID until the token would have expired anyway."""
    if db.get(RevokedToken, claims.jti) is None:
        db.add(RevokedToken(jti=claims.jti, user_id=claims.user_id,
                            expires_at=claims.expires_at))
    # Housekeeping: expired tokens are rejected by their signature check already.
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(UTC)))
    db.commit()


def is_token_revoked(db: Session, jti: str) -> bool:
    return db.get(RevokedToken, jti) is not None
