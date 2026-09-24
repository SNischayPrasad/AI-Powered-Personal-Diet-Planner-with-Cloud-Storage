"""Application configuration.

All configuration comes from environment variables (optionally loaded from a `.env` file),
following the Twelve-Factor App principle "store config in the environment". The same code
therefore runs unchanged on a laptop, in CI and in the cloud — only the variables differ:

    Local development          Cloud deployment
    -----------------          ----------------
    DATABASE_URL=sqlite:///…   DATABASE_URL=postgresql://…  (Supabase / Neon / AWS RDS)
    STORAGE_PROVIDER=local     STORAGE_PROVIDER=s3          (AWS S3 / Supabase Storage / R2)
    AI_PROVIDER=rule_based     AI_PROVIDER=anthropic        (optional, with automatic fallback)

Secrets (JWT signing key, API keys, cloud credentials) are never hard-coded; see `.env.example`.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

API_PREFIX = "/api"  # every REST route lives under /api (frontend and API can share a domain)
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Typed, validated settings. Field names map to upper-case environment variables,
    e.g. `database_url` ← `DATABASE_URL`."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application -------------------------------------------------------------------
    app_name: str = "AI Diet Planner"
    app_version: str = "1.0.0"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"

    # --- Security ----------------------------------------------------------------------
    jwt_secret_key: str = ""  # REQUIRED in production; a temporary key is used in development
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)
    bcrypt_rounds: int = Field(default=12, ge=4, le=16)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    trust_proxy_headers: bool = False  # set true behind a load balancer / CDN (Render, Vercel)
    rate_limit_auth_per_minute: int = Field(default=10, ge=1)
    rate_limit_generate_per_minute: int = Field(default=20, ge=1)

    # --- Cloud database ------------------------------------------------------------------
    database_url: str = "sqlite:///./data/diet_planner.db"
    db_echo: bool = False
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=5, ge=0)

    # --- Cloud object storage --------------------------------------------------------------
    storage_provider: Literal["local", "s3"] = "local"
    storage_bucket: str = "diet-planner-files"
    local_storage_dir: str = "./data/object_storage"
    s3_endpoint_url: str | None = None  # leave empty for AWS; set for MinIO / Supabase / R2
    s3_region: str = "us-east-1"
    s3_access_key_id: str | None = None  # empty → boto3 default chain (IAM role on AWS)
    s3_secret_access_key: str | None = None
    s3_force_path_style: bool = False  # true for MinIO and Supabase Storage
    max_upload_mb: float = Field(default=4, gt=0)
    max_files_per_user: int = Field(default=50, ge=1)  # simple quota to control storage cost

    # --- AI diet planner -----------------------------------------------------------------
    ai_provider: Literal["rule_based", "anthropic", "openai_compatible"] = "rule_based"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5"
    ai_effort: Literal["low", "medium", "high"] | None = "low"  # blank: omit (older models)
    ai_timeout_seconds: float = Field(default=45, gt=0)
    openai_compat_base_url: str | None = None
    openai_compat_api_key: str | None = None
    openai_compat_model: str | None = None

    # --- Observability / frontend ------------------------------------------------------------
    metrics_enabled: bool = True
    frontend_dist_dir: str | None = None  # e.g. "frontend/dist" to serve the SPA from the API

    @field_validator(
        "s3_endpoint_url",
        "s3_access_key_id",
        "s3_secret_access_key",
        "anthropic_api_key",
        "openai_compat_base_url",
        "openai_compat_api_key",
        "openai_compat_model",
        "frontend_dist_dir",
        "ai_effort",
        mode="before",
    )
    @classmethod
    def _blank_means_unset(cls, value: object) -> object:
        # `KEY=` in a .env file arrives as an empty string; treat it as "not configured".
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _require_strong_secret_in_production(self) -> "Settings":
        if self.environment == "production" and len(self.jwt_secret_key) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                "JWT_SECRET_KEY must be a random string of at least "
                f"{MIN_JWT_SECRET_LENGTH} characters in production."
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)

    def resolve_path(self, value: str) -> Path:
        """Resolve a possibly-relative path against the project root (not the current
        working directory), so the app behaves the same wherever it is started from."""
        path = Path(value)
        return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


@lru_cache
def get_settings() -> Settings:
    """Settings are read once per process and cached."""
    return Settings()
