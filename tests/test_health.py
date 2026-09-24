"""Architecture-level behaviour: health checks, request tracing, error envelope,
security headers, CORS, metrics and configuration safety."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import create_app
from backend.config import PROJECT_ROOT, Settings
from cloud.database_service import resolve_sqlite_url
from tests.helpers import EXTERNAL_TEST_DATABASE_URL, make_settings


def test_liveness_endpoint_reports_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_endpoint_checks_the_database(client):
    response = client.get("/api/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"


def test_every_response_gets_a_request_id(client):
    response = client.get("/api/health")

    assert len(response.headers["X-Request-ID"]) >= 8


def test_client_supplied_request_id_is_propagated(client):
    response = client.get("/api/health", headers={"X-Request-ID": "trace-abc-123"})

    assert response.headers["X-Request-ID"] == "trace-abc-123"


def test_oversized_or_unsafe_request_id_is_replaced(client):
    # Prevents log injection / log flooding through a client-controlled header.
    response = client.get("/api/health", headers={"X-Request-ID": "x" * 200})

    assert response.headers["X-Request-ID"] != "x" * 200


def test_unknown_route_returns_json_error_envelope_with_request_id(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_unexpected_exception_returns_generic_500_without_leaking_details(settings):
    app = create_app(settings)

    @app.get("/api/boom")
    def boom():
        raise RuntimeError("database password is hunter2")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "hunter2" not in response.text
    assert response.headers["X-Request-ID"]


def test_api_responses_carry_security_headers(client):
    response = client.get("/api/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"


def test_cors_allows_the_configured_frontend_origin(client):
    response = client.options(
        "/api/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_does_not_allow_unknown_origins(client):
    response = client.options(
        "/api/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_metrics_endpoint_counts_requests_by_route_template(client):
    client.get("/api/health")
    client.get("/api/health")

    metrics = client.get("/api/metrics").text

    assert 'http_requests_total{method="GET",route="/api/health",status="200"} 2' in metrics


def test_metrics_endpoint_can_be_disabled(tmp_path):
    app = create_app(make_settings(tmp_path, metrics_enabled=False))

    with TestClient(app) as client:
        assert client.get("/api/metrics").status_code == 404


def test_system_status_describes_providers_without_exposing_secrets(client, settings):
    body = client.get("/api/system/status").json()

    assert body["database_provider"] == ("postgresql" if EXTERNAL_TEST_DATABASE_URL else "sqlite")
    assert body["ai_provider"] == "rule_based"
    assert settings.jwt_secret_key not in str(body)


def test_production_refuses_to_start_without_a_strong_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", jwt_secret_key="too-short")


def test_development_without_jwt_secret_uses_a_temporary_key(tmp_path):
    app = create_app(make_settings(tmp_path, environment="development", jwt_secret_key=""))

    assert len(app.state.settings.jwt_secret_key) >= 32


def test_blank_optional_settings_from_env_file_are_treated_as_unset(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("S3_ENDPOINT_URL=\nANTHROPIC_API_KEY=\nFRONTEND_DIST_DIR=\n")

    settings = Settings(_env_file=env_file)

    assert settings.s3_endpoint_url is None
    assert settings.anthropic_api_key is None
    assert settings.frontend_dist_dir is None


def test_cors_origins_are_parsed_from_a_comma_separated_string():
    settings = Settings(_env_file=None, cors_origins=" https://a.example , https://b.example ,")

    assert settings.cors_origin_list == ["https://a.example", "https://b.example"]


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "sqlite:///./data/app.db",
            f"sqlite:///{(PROJECT_ROOT / 'data' / 'app.db').as_posix()}",
        ),
        ("sqlite:///:memory:", "sqlite:///:memory:"),
        ("sqlite:////var/lib/app.db", "sqlite:////var/lib/app.db"),
        ("sqlite:///C:/data/app.db", "sqlite:///C:/data/app.db"),
        ("postgresql://u:p@db.example:5432/app", "postgresql://u:p@db.example:5432/app"),
    ],
)
def test_relative_sqlite_paths_resolve_against_the_project_root(url, expected):
    assert resolve_sqlite_url(url, base_dir=PROJECT_ROOT) == expected


def test_database_file_is_created_on_startup(tmp_path):
    db_file = Path(tmp_path) / "nested" / "dir" / "app.db"
    app = create_app(make_settings(tmp_path, database_url=f"sqlite:///{db_file.as_posix()}"))

    with TestClient(app):
        pass

    assert db_file.exists()
