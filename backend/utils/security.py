"""Password hashing and JWT access tokens.

Passwords
    Stored only as **bcrypt** hashes: slow on purpose (work factor = ``BCRYPT_ROUNDS``) and
    salted, so identical passwords produce different hashes and leaked hashes are expensive
    to crack. bcrypt reads at most 72 bytes, so longer passwords are rejected at validation.

Access tokens (JWT)
    After login the API issues a signed token ``header.payload.signature`` containing:
    ``sub`` (user id), ``jti`` (unique token id, used for logout), ``iat``/``exp`` (issued /
    expiry time) and ``type``. The signature (HMAC-SHA256 with ``JWT_SECRET_KEY``) lets any
    server instance verify the token without a session store — this is what makes the API
    *stateless* and easy to scale horizontally.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from backend.utils.errors import AuthenticationError

TOKEN_TYPE = "access"  # noqa: S105 — claim value, not a secret


def hash_password(password: str, rounds: int = 12) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time comparison inside bcrypt; malformed hashes fail closed."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class AccessToken:
    token: str
    jti: str
    expires_at: datetime
    expires_in: int  # seconds


@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    jti: str
    expires_at: datetime


def create_access_token(
    user_id: str,
    *,
    secret: str,
    algorithm: str,
    expires_minutes: int,
    now: datetime | None = None,
) -> AccessToken:
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=expires_minutes)
    jti = uuid.uuid4().hex
    payload = {
        "sub": user_id,
        "jti": jti,
        "type": TOKEN_TYPE,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, secret, algorithm=algorithm)
    return AccessToken(token=token, jti=jti, expires_at=expires_at,
                       expires_in=expires_minutes * 60)


def decode_access_token(token: str, *, secret: str, algorithm: str) -> TokenClaims:
    """Verify signature, expiry and required claims. Only the configured algorithm is
    accepted, which blocks ``alg: none`` and algorithm-confusion attacks."""
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
            options={"require": ["sub", "jti", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError(
            "Your session has expired. Please log in again.", code="token_expired"
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid authentication token.", code="invalid_token") from exc

    if payload.get("type") != TOKEN_TYPE:
        raise AuthenticationError("Invalid authentication token.", code="invalid_token")
    return TokenClaims(
        user_id=str(payload["sub"]),
        jti=str(payload["jti"]),
        expires_at=datetime.fromtimestamp(payload["exp"], UTC),
    )
