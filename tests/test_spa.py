"""Serving the built React app from the API (single-container deployments: Docker, Render)."""

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from tests.helpers import make_settings

INDEX_HTML = "<!doctype html><title>AI Diet Planner</title><div id=root></div>"


@pytest.fixture
def dist(tmp_path):
    folder = tmp_path / "dist"
    (folder / "assets").mkdir(parents=True)
    (folder / "index.html").write_text(INDEX_HTML)
    (folder / "assets" / "app.js").write_text("console.log('app');")
    (folder / "favicon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    return folder


@pytest.fixture
def spa_client(tmp_path, dist):
    app = create_app(make_settings(tmp_path, frontend_dist_dir=str(dist)))
    with TestClient(app) as client:
        yield client


def test_the_root_url_serves_the_react_app(spa_client):
    response = spa_client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "AI Diet Planner" in response.text


@pytest.mark.parametrize("path", ["/dashboard", "/plans/3f2c-demo", "/files"])
def test_client_side_routes_fall_back_to_index_html(spa_client, path):
    response = spa_client.get(path)

    assert response.status_code == 200
    assert response.text == INDEX_HTML


def test_built_assets_and_public_files_are_served(spa_client):
    script = spa_client.get("/assets/app.js")
    icon = spa_client.get("/favicon.svg")

    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert icon.headers["content-type"].startswith("image/svg+xml")


def test_api_routes_still_take_priority(spa_client):
    assert spa_client.get("/api/health").json()["status"] == "ok"


def test_unknown_api_paths_stay_json_404s_instead_of_html(spa_client):
    response = spa_client.get("/api/not-a-route")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_files_outside_the_build_folder_are_never_served(spa_client, tmp_path):
    (tmp_path / "secret.txt").write_text("top secret")

    response = spa_client.get("/%2e%2e/secret.txt")

    assert "top secret" not in response.text


def test_html_pages_get_a_strict_content_security_policy(spa_client):
    policy = spa_client.get("/dashboard").headers["content-security-policy"]

    assert "default-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "script-src 'self'" in policy


def test_without_a_frontend_build_the_service_is_api_only(client):
    assert client.get("/").status_code == 404
