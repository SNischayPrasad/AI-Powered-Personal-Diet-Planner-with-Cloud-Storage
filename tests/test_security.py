"""Unit tests for password hashing, JWT handling and the rate limiter."""

import jwt
import pytest

from backend.utils.errors import AuthenticationError
from backend.utils.rate_limiter import SlidingWindowRateLimiter
from backend.utils.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "unit-test-signing-key-unit-test-signing-key"


def test_same_password_hashes_differently_each_time_but_both_verify():
    first = hash_password("S3cret-pass", rounds=4)
    second = hash_password("S3cret-pass", rounds=4)

    assert first != second  # random salt per hash
    assert verify_password("S3cret-pass", first)
    assert verify_password("S3cret-pass", second)


def test_wrong_password_does_not_verify():
    assert not verify_password("wrong-pass1", hash_password("S3cret-pass", rounds=4))


def test_malformed_hash_fails_closed_instead_of_raising():
    assert verify_password("anything1", "not-a-bcrypt-hash") is False


def test_access_token_round_trip_preserves_identity_and_expiry():
    issued = create_access_token("user-123", secret=SECRET, algorithm="HS256", expires_minutes=30)

    claims = decode_access_token(issued.token, secret=SECRET, algorithm="HS256")

    assert claims.user_id == "user-123"
    assert claims.jti == issued.jti
    assert issued.expires_in == 30 * 60
    assert claims.expires_at == issued.expires_at.replace(microsecond=0)


def test_every_token_gets_a_unique_id_for_revocation():
    first = create_access_token("user-1", secret=SECRET, algorithm="HS256", expires_minutes=5)
    second = create_access_token("user-1", secret=SECRET, algorithm="HS256", expires_minutes=5)

    assert first.jti != second.jti


def test_tampered_token_is_rejected():
    token = create_access_token("user-1", secret=SECRET, algorithm="HS256", expires_minutes=5)
    header, payload, signature = token.token.split(".")
    altered_payload = payload[:-2] + ("AA" if payload[-2:] != "AA" else "BB")
    tampered = ".".join([header, altered_payload, signature])

    with pytest.raises(AuthenticationError) as error:
        decode_access_token(tampered, secret=SECRET, algorithm="HS256")

    assert error.value.code == "invalid_token"


def test_token_of_a_different_type_is_rejected():
    refresh_like = jwt.encode(
        {"sub": "user-1", "jti": "j", "type": "refresh", "iat": 1, "exp": 4_102_444_800},
        SECRET,
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError):
        decode_access_token(refresh_like, secret=SECRET, algorithm="HS256")


def test_rate_limiter_blocks_after_the_limit_and_recovers_when_the_window_slides():
    now = [1_000.0]
    limiter = SlidingWindowRateLimiter(clock=lambda: now[0])

    assert limiter.hit("login:1.2.3.4", limit=2, window_seconds=60) is None
    assert limiter.hit("login:1.2.3.4", limit=2, window_seconds=60) is None
    assert limiter.hit("login:1.2.3.4", limit=2, window_seconds=60) == pytest.approx(60.0)

    now[0] += 61
    assert limiter.hit("login:1.2.3.4", limit=2, window_seconds=60) is None


def test_rate_limiter_tracks_each_key_independently():
    limiter = SlidingWindowRateLimiter(clock=lambda: 0.0)

    assert limiter.hit("login:a", limit=1, window_seconds=60) is None
    assert limiter.hit("login:b", limit=1, window_seconds=60) is None
    assert limiter.hit("login:a", limit=1, window_seconds=60) is not None
