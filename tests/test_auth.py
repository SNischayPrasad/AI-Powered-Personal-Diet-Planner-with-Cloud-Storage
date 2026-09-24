"""Authentication — TC-01 to TC-05 and TC-19 (see docs/16-testing.md)."""

import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app import create_app
from backend.models.db_models import User
from backend.utils.security import create_access_token
from tests.helpers import DEFAULT_PASSWORD, TEST_JWT_SECRET, auth_headers, make_settings, register


# --- TC-01: new user registration ---------------------------------------------------------
def test_tc01_register_new_user_returns_token_and_public_profile(client):
    response = client.post(
        "/api/register",
        json={"name": "Asha Rao", "email": "Asha.Rao@Example.com", "password": DEFAULT_PASSWORD},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] == 60 * 60
    assert body["user"]["email"] == "asha.rao@example.com"  # normalised to lower-case
    assert body["user"]["name"] == "Asha Rao"
    assert "password" not in response.text.lower()


def test_passwords_are_stored_as_salted_bcrypt_hashes(client, app):
    register(client, email="hash@example.com")

    with app.state.db.session_factory() as db:
        stored = db.scalar(select(User.password_hash).where(User.email == "hash@example.com"))

    assert stored != DEFAULT_PASSWORD
    assert stored.startswith("$2b$")


# --- TC-02: existing email registration --------------------------------------------------
def test_tc02_register_with_existing_email_is_rejected_case_insensitively(client):
    register(client, email="taken@example.com")

    response = client.post(
        "/api/register",
        json={"name": "Someone Else", "email": "TAKEN@example.com", "password": DEFAULT_PASSWORD},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_already_registered"


@pytest.mark.parametrize(
    "password",
    [
        "short1",  # fewer than 8 characters
        "onlyletters",  # no digit
        "1234567890",  # no letter
        "a1" * 37,  # 74 characters — above bcrypt's 72-byte limit
        "é" * 40 + "1",  # 41 characters but 81 bytes in UTF-8
    ],
)
def test_register_rejects_weak_or_unsupported_passwords(client, password):
    response = client.post(
        "/api/register", json={"name": "Weak", "email": "weak@example.com", "password": password}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "No Email", "email": "not-an-email", "password": DEFAULT_PASSWORD},
        {"name": "   ", "email": "blank@example.com", "password": DEFAULT_PASSWORD},
        {"email": "missing-name@example.com", "password": DEFAULT_PASSWORD},
    ],
)
def test_register_rejects_invalid_input(client, payload):
    assert client.post("/api/register", json=payload).status_code == 422


# --- TC-03: valid login --------------------------------------------------------------------
def test_tc03_login_with_valid_credentials_returns_a_working_token(client):
    register(client, email="login@example.com")

    response = client.post(
        "/api/login", json={"email": "LOGIN@example.com", "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    assert client.post("/api/logout", headers=auth_headers(token)).status_code == 200


# --- TC-04: invalid login --------------------------------------------------------------------
def test_tc04_login_with_wrong_password_is_rejected(client):
    register(client, email="wrong-pw@example.com")

    response = client.post(
        "/api/login", json={"email": "wrong-pw@example.com", "password": "Wr0ngPassword!"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_error_does_not_reveal_whether_an_email_is_registered(client):
    register(client, email="exists@example.com")

    wrong_password = client.post(
        "/api/login", json={"email": "exists@example.com", "password": "Wr0ngPassword!"}
    )
    unknown_email = client.post(
        "/api/login", json={"email": "nobody@example.com", "password": "Wr0ngPassword!"}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["error"]["message"] == unknown_email.json()["error"]["message"]


# --- TC-05: unauthorized access ------------------------------------------------------------
def test_tc05_protected_endpoint_without_token_is_rejected(client):
    response = client.post("/api/logout")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "not_authenticated"


@pytest.mark.parametrize("token", ["garbage", "a.b.c", ""])
def test_malformed_tokens_are_rejected(client, token):
    response = client.post("/api/logout", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def _claims(user_id: str) -> dict:
    now = int(time.time())
    return {"sub": user_id, "jti": "forged-jti", "type": "access", "iat": now, "exp": now + 600}


def test_token_signed_with_a_different_secret_is_rejected(client):
    user_id = register(client)["user"]["id"]
    forged = jwt.encode(_claims(user_id), "attacker-controlled-secret-" * 2, algorithm="HS256")

    response = client.post("/api/logout", headers=auth_headers(forged))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_unsigned_alg_none_token_is_rejected(client):
    user_id = register(client)["user"]["id"]
    unsigned = jwt.encode(_claims(user_id), "", algorithm="none")

    assert client.post("/api/logout", headers=auth_headers(unsigned)).status_code == 401


def test_expired_token_is_rejected_with_a_specific_error_code(client):
    user_id = register(client)["user"]["id"]
    expired = create_access_token(
        user_id,
        secret=TEST_JWT_SECRET,
        algorithm="HS256",
        expires_minutes=5,
        now=datetime.now(UTC) - timedelta(minutes=10),
    ).token

    response = client.post("/api/logout", headers=auth_headers(expired))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_expired"


def test_token_for_a_deleted_account_is_rejected(client, app):
    body = register(client, email="deleted@example.com")
    with app.state.db.session_factory() as db:
        db.delete(db.get(User, body["user"]["id"]))
        db.commit()

    response = client.post("/api/logout", headers=auth_headers(body["access_token"]))

    assert response.status_code == 401


# --- TC-19: logout -----------------------------------------------------------------------------
def test_tc19_logout_revokes_the_token_server_side(client):
    token = register(client)["access_token"]

    first = client.post("/api/logout", headers=auth_headers(token))
    second = client.post("/api/logout", headers=auth_headers(token))

    assert first.status_code == 200
    assert second.status_code == 401
    assert second.json()["error"]["code"] == "token_revoked"


def test_logging_out_one_session_leaves_other_sessions_valid(client):
    first_token = register(client, email="two-devices@example.com")["access_token"]
    second_token = client.post(
        "/api/login", json={"email": "two-devices@example.com", "password": DEFAULT_PASSWORD}
    ).json()["access_token"]

    client.post("/api/logout", headers=auth_headers(first_token))

    assert client.post("/api/logout", headers=auth_headers(second_token)).status_code == 200


# --- Abuse protection & monitoring ----------------------------------------------------------------
def test_login_attempts_are_rate_limited_per_client(tmp_path):
    app = create_app(make_settings(tmp_path, rate_limit_auth_per_minute=3))
    attempt = {"email": "brute@example.com", "password": "Wr0ngPassword!"}

    with TestClient(app) as client:
        responses = [client.post("/api/login", json=attempt) for _ in range(4)]

    assert [r.status_code for r in responses] == [401, 401, 401, 429]
    assert responses[-1].json()["error"]["code"] == "rate_limited"
    assert int(responses[-1].headers["Retry-After"]) >= 1


def test_rate_limit_uses_forwarded_client_ip_only_when_proxy_is_trusted(tmp_path):
    app = create_app(
        make_settings(tmp_path, rate_limit_auth_per_minute=1, trust_proxy_headers=True)
    )
    attempt = {"email": "proxy@example.com", "password": "Wr0ngPassword!"}

    with TestClient(app) as client:
        first = client.post("/api/login", json=attempt, headers={"X-Forwarded-For": "1.1.1.1"})
        other_ip = client.post("/api/login", json=attempt, headers={"X-Forwarded-For": "2.2.2.2"})
        same_ip = client.post("/api/login", json=attempt, headers={"X-Forwarded-For": "1.1.1.1"})

    assert [first.status_code, other_ip.status_code, same_ip.status_code] == [401, 401, 429]


def test_failed_logins_are_counted_in_metrics(client):
    client.post("/api/login", json={"email": "who@example.com", "password": "Wr0ngPassword!"})

    metrics = client.get("/api/metrics").text

    assert 'auth_events_total{event="login_failure"} 1' in metrics
