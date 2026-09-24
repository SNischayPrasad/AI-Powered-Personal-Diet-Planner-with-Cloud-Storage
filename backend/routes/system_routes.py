"""Health, readiness, status and metrics endpoints.

* ``/api/health``       — *liveness*: the process is up. Load balancers and platforms such as
                          Render, AWS App Runner or Kubernetes restart instances that fail it.
* ``/api/health/ready`` — *readiness*: the instance can reach its cloud dependencies
                          (database, object storage). Traffic is only routed to ready instances.
* ``/api/system/status``— which cloud providers this deployment is wired to (no secrets).
* ``/api/metrics``      — Prometheus-format counters for monitoring dashboards.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.config import API_PREFIX
from backend.models.schemas import HealthResponse, ReadinessResponse, SystemStatus
from backend.utils.dependencies import AppMetrics, AppSettings
from backend.utils.errors import NotFoundError

router = APIRouter(prefix=API_PREFIX, tags=["System"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health(settings: AppSettings) -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name, version=settings.app_version)


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe (checks the database and object storage)",
    responses={503: {"model": ReadinessResponse, "description": "A dependency is down"}},
)
def readiness(request: Request) -> JSONResponse:
    state = request.app.state
    checks = {
        "database": "ok" if state.db.health_check() else "unavailable",
        "storage": "ok" if state.storage.health_check() else "unavailable",
    }
    healthy = all(result == "ok" for result in checks.values())
    body = ReadinessResponse(status="ready" if healthy else "degraded", checks=checks)
    return JSONResponse(status_code=200 if healthy else 503, content=body.model_dump())


@router.get("/system/status", response_model=SystemStatus, summary="Deployment information")
def system_status(request: Request, settings: AppSettings) -> SystemStatus:
    return SystemStatus(
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database_provider=request.app.state.db.provider_name,
        storage_provider=request.app.state.storage.provider_name,
        ai_provider=settings.ai_provider,
        max_upload_mb=settings.max_upload_mb,
    )


@router.get("/metrics", include_in_schema=False)
def metrics(settings: AppSettings, app_metrics: AppMetrics) -> PlainTextResponse:
    if not settings.metrics_enabled:
        raise NotFoundError("Metrics are disabled.")
    return PlainTextResponse(
        app_metrics.render_prometheus(), media_type="text/plain; version=0.0.4"
    )
