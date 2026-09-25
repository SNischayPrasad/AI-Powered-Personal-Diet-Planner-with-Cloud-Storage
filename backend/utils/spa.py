"""Serve the built React single-page app from the API.

Used by single-container deployments (Docker, Render, AWS App Runner): one service, one URL,
no CORS. Set ``FRONTEND_DIST_DIR`` to the folder produced by ``npm run build``.

* ``/api/*``        — the REST API (registered first, so it always wins);
* ``/assets/*``     — fingerprinted JS/CSS/fonts, cacheable for a year;
* any other path   — a real file from the build folder, or ``index.html`` so that React
                     Router can render client-side routes such as ``/dashboard``.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import API_PREFIX
from backend.utils.errors import NotFoundError

logger = logging.getLogger("diet_planner.app")


class ImmutableStaticFiles(StaticFiles):
    """Vite puts a content hash in every asset name, so assets never change in place."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def mount_frontend(app: FastAPI, dist: Path) -> bool:
    dist = dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        logger.warning("FRONTEND_DIST_DIR %s has no index.html; serving the API only.", dist)
        return False

    if (dist / "assets").is_dir():
        app.mount("/assets", ImmutableStaticFiles(directory=dist / "assets"), name="assets")

    api_root = API_PREFIX.strip("/")

    @app.get("/{full_path:path}", include_in_schema=False)
    def single_page_app(full_path: str) -> FileResponse:
        if full_path == api_root or full_path.startswith(f"{api_root}/"):
            raise NotFoundError("The requested resource was not found.")
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and dist in candidate.parents:
            return FileResponse(candidate)  # favicon.svg and other public files
        # index.html must never be cached, or users would keep loading old asset names.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    logger.info("Serving the web app from %s", dist)
    return True
