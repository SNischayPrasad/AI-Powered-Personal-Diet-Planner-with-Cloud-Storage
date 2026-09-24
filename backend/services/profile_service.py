"""Profile management logic."""

from sqlalchemy.orm import Session

from backend.models.db_models import User
from backend.models.schemas import ProfileUpdate


def update_profile(db: Session, user: User, data: ProfileUpdate) -> User:
    """Replace the user's diet profile. The email and password are deliberately not
    editable here — they are not part of ProfileUpdate."""
    if data.name is not None:
        user.name = data.name
    user.age = data.age
    user.sex = data.sex.value
    user.height_cm = data.height_cm
    user.weight_kg = data.weight_kg
    user.activity_level = data.activity_level.value
    user.dietary_preference = data.dietary_preference.value
    user.goal = data.goal.value
    user.allergies = [allergen.value for allergen in data.allergies]
    user.cuisine_preference = data.cuisine_preference.value
    db.commit()
    db.refresh(user)
    return user
