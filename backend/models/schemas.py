"""API schemas (Pydantic models).

Schemas define exactly what the API accepts and returns. Incoming data is validated
*before* it reaches business logic, and responses never include internal fields such as
password hashes or storage credentials.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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


class UserPublic(BaseModel):
    """The user as the API shows it — never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — OAuth2 token type, not a secret
    expires_in: int = Field(description="Seconds until the token expires.")
    user: UserPublic


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
