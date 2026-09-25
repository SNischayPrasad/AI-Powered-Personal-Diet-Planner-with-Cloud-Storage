"""Deployment configuration stays in sync with the code (Docker, Render, Vercel)."""

import json
import re

from fastapi import FastAPI

from backend.config import PROJECT_ROOT


def test_vercel_entry_point_exposes_the_fastapi_app():
    from api.index import app

    assert isinstance(app, FastAPI)


def test_vercel_config_points_at_real_files_and_keeps_api_routes_on_python():
    config = json.loads((PROJECT_ROOT / "vercel.json").read_text(encoding="utf-8"))

    for function_path in config["functions"]:
        assert (PROJECT_ROOT / function_path).is_file()
    api_rewrite, spa_rewrite = config["rewrites"]
    assert api_rewrite == {"source": "/api/(.*)", "destination": "/api/index"}
    assert not re.fullmatch(spa_rewrite["source"].lstrip("/"), "api/health")
    assert re.fullmatch(spa_rewrite["source"].lstrip("/"), "dashboard")


def test_render_health_check_uses_an_existing_route(client):
    blueprint = (PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8")
    path = re.search(r"healthCheckPath:\s*(\S+)", blueprint).group(1)

    assert client.get(path).status_code == 200


def test_dockerfile_runs_as_non_root_and_serves_the_frontend():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert re.search(r"^USER appuser$", dockerfile, re.MULTILINE)
    assert "FRONTEND_DIST_DIR=/app/frontend/dist" in dockerfile
    for package in ("backend", "ai_engine", "cloud"):
        assert f"COPY {package}/ {package}/" in dockerfile


def test_secrets_never_enter_the_docker_build_context():
    ignored = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8").split()

    assert ".env" in ignored
    assert "data" in ignored
