"""FastAPI application factory — the entry point of the backend.

Run locally (from the project root):

    uvicorn backend.app:app --reload

``create_app()`` wires together configuration, the cloud database, middleware, error handlers
and the REST routes. Tests call it with their own settings to get an isolated app.
"""

import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import backend.models.db_models  # noqa: F401  (registers the tables with SQLAlchemy)
from backend.config import API_PREFIX, PROJECT_ROOT, Settings, get_settings
from backend.routes import auth_routes, system_routes
from backend.utils.errors import register_exception_handlers
from backend.utils.logging_config import configure_logging
from backend.utils.metrics import Metrics
from backend.utils.middleware import register_request_middleware
from backend.utils.rate_limiter import SlidingWindowRateLimiter
from cloud.database_service import DatabaseService

logger = logging.getLogger("diet_planner.app")

API_DESCRIPTION = """
Cloud-based **AI-powered personal diet planner** — REST API.

* **Auth**: register / login return a JWT. Send it as `Authorization: Bearer <token>`.
* **Data**: every plan and file is scoped to the authenticated user.
* **Disclaimer**: generated plans are educational, general-wellness examples — *not* medical
  or clinical nutrition advice.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)

    if not settings.jwt_secret_key:
        # Development convenience only — production refuses to start without a real secret.
        settings = settings.model_copy(update={"jwt_secret_key": secrets.token_urlsafe(48)})
        logger.warning(
            "JWT_SECRET_KEY is not set; using a temporary key. Sessions end when the server "
            "restarts. Set JWT_SECRET_KEY in your .env file."
        )

    database = DatabaseService(settings.database_url, base_dir=PROJECT_ROOT, echo=settings.db_echo)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.create_tables()
        logger.info(
            "%s v%s started (environment=%s, database=%s, ai=%s)",
            settings.app_name,
            settings.app_version,
            settings.environment,
            database.provider_name,
            settings.ai_provider,
        )
        yield
        database.dispose()

    app = FastAPI(
        title="AI-Powered Personal Diet Planner API",
        version=settings.app_version,
        description=API_DESCRIPTION,
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.state.settings = settings
    app.state.db = database
    app.state.metrics = Metrics()
    app.state.rate_limiter = SlidingWindowRateLimiter()

    register_exception_handlers(app)
    register_request_middleware(app)
    # CORS: only the configured frontend origins may call the API from a browser.
    # Tokens travel in the Authorization header (not cookies), so credentials stay disabled.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
        max_age=600,
    )

    app.include_router(system_routes.router)
    app.include_router(auth_routes.router)
    return app


app = create_app()
