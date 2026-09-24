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
from sqlalchemy.exc import SQLAlchemyError

import backend.models.db_models  # noqa: F401  (registers the tables with SQLAlchemy)
from ai_engine.llm_providers import create_llm_provider
from ai_engine.planner import DietPlanner
from backend.config import API_PREFIX, PROJECT_ROOT, Settings, get_settings
from backend.routes import auth_routes, file_routes, plan_routes, profile_routes, system_routes
from backend.utils.errors import register_exception_handlers
from backend.utils.logging_config import configure_logging
from backend.utils.metrics import Metrics
from backend.utils.middleware import register_request_middleware
from backend.utils.rate_limiter import SlidingWindowRateLimiter
from cloud.database_service import DatabaseService
from cloud.storage_service import create_storage_service

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

    database = DatabaseService(
        settings.database_url,
        base_dir=PROJECT_ROOT,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )
    storage = create_storage_service(
        settings.storage_provider,
        bucket=settings.storage_bucket,
        local_dir=settings.resolve_path(settings.local_storage_dir),
        region=settings.s3_region,
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
        force_path_style=settings.s3_force_path_style,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            database.create_tables()
        except SQLAlchemyError as exc:
            # Start anyway: /api/health/ready reports "degraded" and data requests get a 503
            # until the database is reachable again (tables are then created automatically).
            logger.error("Database unavailable at startup (%s); running in degraded mode.",
                         exc.__class__.__name__)
        logger.info(
            "%s v%s started (environment=%s, database=%s, storage=%s, ai=%s)",
            settings.app_name,
            settings.app_version,
            settings.environment,
            database.provider_name,
            storage.provider_name,
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
    app.state.storage = storage
    app.state.metrics = Metrics()
    app.state.rate_limiter = SlidingWindowRateLimiter()
    app.state.planner = DietPlanner(
        create_llm_provider(
            settings.ai_provider,
            anthropic_api_key=settings.anthropic_api_key,
            anthropic_model=settings.anthropic_model,
            ai_effort=settings.ai_effort,
            timeout=settings.ai_timeout_seconds,
            openai_base_url=settings.openai_compat_base_url,
            openai_api_key=settings.openai_compat_api_key,
            openai_model=settings.openai_compat_model,
        ),
        ai_requested=settings.ai_provider != "rule_based",
    )

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
    app.include_router(profile_routes.router)
    app.include_router(plan_routes.router)
    app.include_router(file_routes.router)
    return app


app = create_app()
