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
from tests.helpers import make_settings


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
