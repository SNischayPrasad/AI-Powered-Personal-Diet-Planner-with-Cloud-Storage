"""Profile endpoints: read and update the logged-in user's diet profile."""

from fastapi import APIRouter

from backend.config import API_PREFIX
from backend.models.schemas import ProfileUpdate, UserProfile
from backend.services import profile_service
from backend.utils.dependencies import CurrentUser, DbSession

router = APIRouter(prefix=API_PREFIX, tags=["Profile"])


@router.get("/profile", response_model=UserProfile, summary="Get my profile")
def get_profile(user: CurrentUser) -> UserProfile:
    return UserProfile.model_validate(user)


@router.put(
    "/profile",
    response_model=UserProfile,
    summary="Create or update my profile",
    responses={422: {"description": "A value is missing or out of range"}},
)
def update_profile(payload: ProfileUpdate, user: CurrentUser, db: DbSession) -> UserProfile:
    updated = profile_service.update_profile(db, user, payload)
    return UserProfile.model_validate(updated)
