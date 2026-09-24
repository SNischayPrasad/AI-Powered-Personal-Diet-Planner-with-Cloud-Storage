"""API schemas (Pydantic models).

Schemas define exactly what the API accepts and returns. Incoming data is validated
*before* it reaches business logic, and responses never include internal fields such as
password hashes or storage credentials.
"""

from typing import Literal

from pydantic import BaseModel

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
