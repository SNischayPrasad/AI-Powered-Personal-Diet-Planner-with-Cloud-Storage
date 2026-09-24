"""Diet plan endpoints: generate, list, retrieve, delete and export."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, Response, status

from backend.config import API_PREFIX
from backend.models.schemas import GeneratePlanRequest, PlanList, PlanOut
from backend.services import export_service, plan_service
from backend.utils.dependencies import AppMetrics, AppSettings, CurrentUser, DbSession
from backend.utils.rate_limiter import enforce_rate_limit

logger = logging.getLogger("diet_planner.plans")

router = APIRouter(prefix=API_PREFIX, tags=["Diet plans"])


@router.post(
    "/generate-plan",
    response_model=PlanOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and save a personalised diet plan",
    responses={
        400: {"description": "Profile incomplete"},
        422: {"description": "Invalid overrides, or no dishes match the restrictions"},
        429: {"description": "Too many plans generated in the last minute"},
    },
)
def generate_plan(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
    metrics: AppMetrics,
    payload: GeneratePlanRequest | None = None,
) -> PlanOut:
    enforce_rate_limit(
        request, key=f"generate:{user.id}", limit=settings.rate_limit_generate_per_minute
    )
    record = plan_service.generate_plan(
        db, user, payload or GeneratePlanRequest(), planner=request.app.state.diet_engine
    )
    metrics.inc("plans_generated_total", source=record.source)
    logger.info("Diet plan generated",
                extra={"user_id": user.id, "plan_id": record.id, "source": record.source})
    return PlanOut.model_validate(record)


@router.get("/plans", response_model=PlanList, summary="List my saved plans (newest first)")
def list_plans(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PlanList:
    rows, total = plan_service.list_user_plans(db, user.id, limit=limit, offset=offset)
    return PlanList(items=[plan_service.to_summary(row) for row in rows], total=total,
                    limit=limit, offset=offset)


@router.get("/plans/{plan_id}", response_model=PlanOut, summary="Get one of my plans",
            responses={404: {"description": "No such plan for this user"}})
def get_plan(plan_id: str, user: CurrentUser, db: DbSession) -> PlanOut:
    return PlanOut.model_validate(plan_service.get_user_plan(db, user.id, plan_id))


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete one of my plans",
               responses={404: {"description": "No such plan for this user"}})
def delete_plan(plan_id: str, user: CurrentUser, db: DbSession) -> Response:
    plan_service.delete_user_plan(db, user.id, plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/plans/{plan_id}/export",
    summary="Download a plan as JSON or a text report",
    response_class=Response,
    responses={200: {"content": {"application/json": {}, "text/plain": {}}}},
)
def export_plan(
    plan_id: str,
    user: CurrentUser,
    db: DbSession,
    export_format: Annotated[Literal["json", "txt"], Query(alias="format")] = "json",
) -> Response:
    plan = PlanOut.model_validate(plan_service.get_user_plan(db, user.id, plan_id))
    body = (export_service.plan_to_json(plan) if export_format == "json"
            else export_service.plan_to_text(plan).encode("utf-8"))
    filename = export_service.export_filename(plan, export_format)
    return Response(
        content=body,
        media_type=export_service.EXPORT_MEDIA_TYPES[export_format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
