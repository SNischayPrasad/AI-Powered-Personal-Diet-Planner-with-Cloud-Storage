"""Diet plan logic: turn the saved profile into planner input, generate, persist and query.

Authorization rule used by every function here: a plan is looked up by *both* its ID and the
ID of the logged-in user. A plan that belongs to someone else is therefore indistinguishable
from a plan that does not exist (404) — users cannot probe for other people's data.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_engine.diet_engine import GeneratedPlan, NoSuitableMealsError
from ai_engine.nutrition import PlanRequest
from ai_engine.options import ActivityLevel, Allergen, Cuisine, DietaryPreference, Goal, Sex
from backend.models.db_models import DietPlan, User
from backend.models.schemas import GeneratePlanRequest, PlanSummary, UserProfile
from backend.utils.errors import BadRequestError, NotFoundError, UnprocessableError


def build_plan_request(user: User, overrides: GeneratePlanRequest) -> PlanRequest:
    """Combine the saved profile with optional per-plan overrides."""
    if not UserProfile.model_validate(user).profile_complete:
        raise BadRequestError(
            "Complete your profile (age, height, weight, activity level, dietary preference "
            "and goal) before generating a plan.",
            code="profile_incomplete",
        )
    allergies = (overrides.allergies if overrides.allergies is not None
                 else [Allergen(value) for value in user.allergies or []])
    return PlanRequest(
        age=user.age,
        sex=Sex(user.sex or Sex.UNSPECIFIED),
        height_cm=user.height_cm,
        weight_kg=user.weight_kg,
        activity_level=ActivityLevel(user.activity_level),
        dietary_preference=overrides.dietary_preference
        or DietaryPreference(user.dietary_preference),
        goal=overrides.goal or Goal(user.goal),
        allergies=frozenset(allergies),
        cuisine=overrides.cuisine_preference or Cuisine(user.cuisine_preference or Cuisine.ANY),
    )


def save_plan(db: Session, user_id: str, plan: GeneratedPlan) -> DietPlan:
    record = DietPlan(
        user_id=user_id,
        title=plan.title,
        dietary_preference=plan.dietary_preference,
        goal=plan.goal,
        cuisine=plan.cuisine,
        allergies=plan.allergies,
        calorie_target=plan.targets.calories,
        breakfast=plan.meals["breakfast"].model_dump(),
        lunch=plan.meals["lunch"].model_dump(),
        snack=plan.meals["snack"].model_dump(),
        dinner=plan.meals["dinner"].model_dump(),
        nutrition_summary={
            "targets": plan.targets.model_dump(),
            "totals": plan.totals.model_dump(),
            "macro_percentages": plan.macro_percentages,
        },
        hydration_tip=plan.hydration_tip,
        tips=plan.tips,
        disclaimer=plan.disclaimer,
        source=plan.source,
        ai_provider=plan.ai_provider,
        ai_model=plan.ai_model,
        fallback_reason=plan.fallback_reason,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def generate_plan(db: Session, user: User, overrides: GeneratePlanRequest, planner) -> DietPlan:
    """Generate a plan with ``planner`` (anything with ``generate(PlanRequest)``) and save it."""
    request = build_plan_request(user, overrides)
    try:
        plan = planner.generate(request)
    except NoSuitableMealsError as exc:
        raise UnprocessableError(str(exc), code="no_suitable_meals") from exc
    return save_plan(db, user.id, plan)


def get_user_plan(db: Session, user_id: str, plan_id: str) -> DietPlan:
    plan = db.scalar(
        select(DietPlan).where(DietPlan.id == plan_id, DietPlan.user_id == user_id)
    )
    if plan is None:
        raise NotFoundError("Plan not found.")
    return plan


def list_user_plans(
    db: Session, user_id: str, *, limit: int, offset: int
) -> tuple[list[DietPlan], int]:
    total = db.scalar(
        select(func.count()).select_from(DietPlan).where(DietPlan.user_id == user_id)
    )
    rows = db.scalars(
        select(DietPlan)
        .where(DietPlan.user_id == user_id)
        .order_by(DietPlan.created_at.desc(), DietPlan.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), total or 0


def delete_user_plan(db: Session, user_id: str, plan_id: str) -> None:
    db.delete(get_user_plan(db, user_id, plan_id))
    db.commit()


def to_summary(plan: DietPlan) -> PlanSummary:
    return PlanSummary(
        id=plan.id,
        title=plan.title,
        created_at=plan.created_at,
        dietary_preference=plan.dietary_preference,
        goal=plan.goal,
        calorie_target=plan.calorie_target,
        total_calories=plan.nutrition_summary["totals"]["calories"],
        source=plan.source,
    )
