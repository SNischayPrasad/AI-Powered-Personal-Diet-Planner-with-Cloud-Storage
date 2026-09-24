"""Shared pytest fixtures.

Every test gets its own temporary SQLite database and object-storage folder, so tests are
isolated from each other and from the developer's local data. When TEST_DATABASE_URL points
at a real PostgreSQL server (as in CI), every test starts from empty tables instead.
Nothing here talks to a real cloud service.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import backend.models.db_models  # noqa: F401  (registers the tables for drop_all)
from backend.app import create_app
from backend.config import PROJECT_ROOT, Settings
from cloud.database_service import Base, DatabaseService
from tests.helpers import EXTERNAL_TEST_DATABASE_URL, make_settings


@pytest.fixture(autouse=True)
def _fresh_external_database() -> Iterator[None]:
    if EXTERNAL_TEST_DATABASE_URL:
        service = DatabaseService(EXTERNAL_TEST_DATABASE_URL, base_dir=PROJECT_ROOT)
        Base.metadata.drop_all(service.engine)
        service.dispose()
    yield


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
