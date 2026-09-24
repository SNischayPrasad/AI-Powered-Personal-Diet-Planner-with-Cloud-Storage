"""Shared pytest fixtures.

Every test gets its own temporary SQLite database and object-storage folder, so tests are
isolated from each other and from the developer's local data. Nothing here talks to a real
cloud service.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings

TEST_JWT_SECRET = "test-only-signing-key-that-is-long-enough-for-hs256-0123456789"


def make_settings(tmp_path, **overrides) -> Settings:
    """Build isolated settings. Every value is passed explicitly so a developer's own
    environment variables or .env file can never leak into the test run."""
    values = {
        "environment": "test",
        "log_level": "WARNING",
        "database_url": f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        "local_storage_dir": str(tmp_path / "object_storage"),
        "storage_provider": "local",
        "jwt_secret_key": TEST_JWT_SECRET,
        "bcrypt_rounds": 4,  # fast hashing for tests; production uses 12
        "ai_provider": "rule_based",
        "rate_limit_auth_per_minute": 1000,
        "rate_limit_generate_per_minute": 1000,
        "cors_origins": "http://localhost:5173",
        "metrics_enabled": True,
        "frontend_dist_dir": None,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    # Using the client as a context manager runs the app's startup/shutdown (lifespan).
    with TestClient(app) as test_client:
        yield test_client
