"""Cloud database integration — URL handling, relational integrity and TC-20 (database outage)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.app import create_app
from backend.config import PROJECT_ROOT
from backend.models.db_models import DietPlan, User
from cloud.database_service import DatabaseService, normalize_database_url
from tests.helpers import DEFAULT_PASSWORD, auth_headers, complete_profile, make_settings, register


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # Heroku/Render/Supabase-style scheme that SQLAlchemy 2 no longer accepts
        ("postgres://u:p@db.example:5432/app", "postgresql+psycopg2://u:p@db.example:5432/app"),
        ("postgresql://u:p@db.example/app?sslmode=require",
         "postgresql+psycopg2://u:p@db.example/app?sslmode=require"),
        ("postgresql+psycopg2://u:p@db.example/app", "postgresql+psycopg2://u:p@db.example/app"),
        ("postgresql+psycopg://u:p@db.example/app", "postgresql+psycopg://u:p@db.example/app"),
        ("sqlite:///./data/app.db", "sqlite:///./data/app.db"),
    ],
)
def test_cloud_postgres_urls_are_normalised_for_sqlalchemy(url, expected):
    assert normalize_database_url(url) == expected


def test_postgres_connections_use_a_bounded_pool():
    service = DatabaseService("postgres://u:p@db.example/app", base_dir=PROJECT_ROOT,
                              pool_size=3, max_overflow=2)

    assert service.provider_name == "postgresql"
    assert service.engine.pool.size() == 3


def test_foreign_keys_are_enforced_locally_just_like_on_postgres(client, app):
    with app.state.db.session_factory() as db:
        db.add(DietPlan(user_id="no-such-user", title="orphan", dietary_preference="vegan",
                        goal="balanced", cuisine="any", allergies=[], calorie_target=2000,
                        breakfast={}, lunch={}, snack={}, dinner={}, nutrition_summary={},
                        hydration_tip="", tips=[], disclaimer="", source="rule_based"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_deleting_a_user_cascades_to_their_plans(client, app):
    body = register(client)
    complete_profile(client, body["access_token"])
    client.post("/api/generate-plan", json={}, headers=auth_headers(body["access_token"]))

    with app.state.db.session_factory() as db:
        db.delete(db.get(User, body["user"]["id"]))
        db.commit()
        remaining = db.scalar(select(func.count()).select_from(DietPlan))

    assert remaining == 0


# --- TC-20: cloud database failure handling --------------------------------------------------
@pytest.fixture
def unreachable_db_app(tmp_path):
    """A real driver error, not a mock: the database file cannot be opened because its
    parent 'directory' is actually a file — the local equivalent of an unreachable server."""
    blocker = tmp_path / "blocker"
    blocker.write_text("this file sits where the database directory should be")
    url = f"sqlite:///{(blocker / 'db' / 'app.db').as_posix()}"
    return create_app(make_settings(tmp_path, database_url=url))


def test_tc20_app_starts_and_reports_not_ready_when_the_database_is_down(unreachable_db_app):
    with TestClient(unreachable_db_app) as client:
        live = client.get("/api/health")
        ready = client.get("/api/health/ready")

    assert live.status_code == 200  # process is alive: don't restart it
    assert ready.status_code == 503  # but don't send it traffic either
    assert ready.json()["checks"]["database"] == "unavailable"


def test_tc20_requests_needing_the_database_fail_with_a_clear_503(unreachable_db_app):
    with TestClient(unreachable_db_app) as client:
        response = client.post(
            "/api/register",
            json={"name": "Outage", "email": "outage@example.com", "password": DEFAULT_PASSWORD},
        )
        metrics = client.get("/api/metrics").text

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert 'dependency_errors_total{dependency="database"} 1' in metrics


def test_service_recovers_when_the_database_comes_back(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("temporarily in the way")
    app = create_app(make_settings(
        tmp_path, database_url=f"sqlite:///{(blocker / 'app.db').as_posix()}"))

    with TestClient(app) as client:
        assert client.get("/api/health/ready").status_code == 503
        blocker.unlink()  # the "outage" ends
        blocker.mkdir()

        assert client.get("/api/health/ready").status_code == 200
        assert register(client)["access_token"]
