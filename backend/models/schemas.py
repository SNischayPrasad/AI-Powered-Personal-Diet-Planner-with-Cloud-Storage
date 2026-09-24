"""API schemas (Pydantic models).

Schemas define exactly what the API accepts and returns. Incoming data is validated
*before* it reaches business logic, and responses never include internal fields such as
password hashes or storage credentials.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator

from ai_engine.options import ActivityLevel, Allergen, Cuisine, DietaryPreference, Goal, Sex

BCRYPT_MAX_BYTES = 72

# ---------------------------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Asha Demo"])
    email: EmailStr = Field(examples=["asha.demo@example.com"])
    password: str = Field(
        min_length=8,
        max_length=BCRYPT_MAX_BYTES,
        description="8–72 characters, with at least one letter and one number.",
        examples=["Demo-Passw0rd"],
    )

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def _password_policy(cls, value: str) -> str:
        if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
            raise ValueError(f"Password must be at most {BCRYPT_MAX_BYTES} bytes")
        if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
            raise ValueError("Password must contain at least one letter and one number")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()


class UserProfile(BaseModel):
    """The user as the API shows it — never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    age: int | None = None
    sex: Sex | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    activity_level: ActivityLevel | None = None
    dietary_preference: DietaryPreference | None = None
    goal: Goal | None = None
    allergies: list[Allergen] = []
    cuisine_preference: Cuisine = Cuisine.ANY
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def profile_complete(self) -> bool:
        """True once every field the diet planner needs has been filled in."""
        required = (self.age, self.height_cm, self.weight_kg, self.activity_level,
                    self.dietary_preference, self.goal)
        return all(value is not None for value in required)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — OAuth2 token type, not a secret
    expires_in: int = Field(description="Seconds until the token expires.")
    user: UserProfile


# ---------------------------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------------------------


class ProfileUpdate(BaseModel):
    """Demo profile data used to personalise plans. Ranges keep inputs realistic for adults —
    the calorie formulas used are designed for adults."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    age: int = Field(ge=18, le=90, examples=[28])
    sex: Sex = Sex.UNSPECIFIED
    height_cm: float = Field(ge=100, le=250, examples=[165])
    weight_kg: float = Field(ge=30, le=300, examples=[60])
    activity_level: ActivityLevel
    dietary_preference: DietaryPreference
    goal: Goal
    allergies: list[Allergen] = Field(default_factory=list, max_length=len(Allergen) * 2)
    cuisine_preference: Cuisine = Cuisine.ANY

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("allergies")
    @classmethod
    def _deduplicate(cls, value: list[Allergen]) -> list[Allergen]:
        return list(dict.fromkeys(value))


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------------------------
# System / monitoring
# ---------------------------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    checks: dict[str, str]


class SystemStatus(BaseModel):
    app_name: str
    version: str
    environment: str
    database_provider: str
    ai_provider: str
    max_upload_mb: float
