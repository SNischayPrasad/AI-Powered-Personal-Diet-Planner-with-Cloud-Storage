"""Database tables (SQLAlchemy ORM models).

Design notes
------------
* **UUID primary keys** (stored as 36-character strings): IDs cannot be guessed or
  enumerated (``/plans/1``, ``/plans/2`` …), which is a second line of defence behind the
  per-user authorization checks. They also work identically on SQLite and PostgreSQL.
* **user_id foreign keys** on every user-owned table: all queries filter by the logged-in
  user's ID, which is how one user can never read another user's data.
* **UTC timestamps** everywhere, so servers in different regions agree on time.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from cloud.database_service import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every database.

    PostgreSQL stores time zones natively; SQLite does not, so values read back from SQLite
    are naive. This type always stores UTC and always returns an aware UTC datetime."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class User(Base):
    """A registered (synthetic/demo) user account and their diet profile."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))  # bcrypt hash, never the password

    # Profile — empty until the user completes it. Option values are stored as plain strings
    # (see ai_engine/options.py) so the schema is portable across SQLite and PostgreSQL.
    age: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[str | None] = mapped_column(String(20))
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    activity_level: Mapped[str | None] = mapped_column(String(30))
    dietary_preference: Mapped[str | None] = mapped_column(String(30))
    goal: Mapped[str | None] = mapped_column(String(30))
    allergies: Mapped[list[str]] = mapped_column(JSON, default=list)
    cuisine_preference: Mapped[str] = mapped_column(String(20), default="any")

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class DietPlan(Base):
    """A generated diet plan. Each meal is stored as a JSON document so the table stays
    simple while still holding rich meal details (portion, ingredients, macros, reasoning)."""

    __tablename__ = "diet_plans"
    __table_args__ = (Index("ix_diet_plans_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(160))
    # Snapshot of the preferences used for *this* plan (the profile may change later).
    dietary_preference: Mapped[str] = mapped_column(String(30))
    goal: Mapped[str] = mapped_column(String(30))
    cuisine: Mapped[str] = mapped_column(String(20))
    allergies: Mapped[list[str]] = mapped_column(JSON, default=list)
    calorie_target: Mapped[int] = mapped_column(Integer)

    breakfast: Mapped[dict] = mapped_column(JSON)
    lunch: Mapped[dict] = mapped_column(JSON)
    snack: Mapped[dict] = mapped_column(JSON)
    dinner: Mapped[dict] = mapped_column(JSON)
    nutrition_summary: Mapped[dict] = mapped_column(JSON)  # targets, totals, macro percentages
    hydration_tip: Mapped[str] = mapped_column(Text)
    tips: Mapped[list[str]] = mapped_column(JSON, default=list)
    disclaimer: Mapped[str] = mapped_column(Text)

    # Provenance: which engine produced the plan, and why the AI was skipped if it was.
    source: Mapped[str] = mapped_column(String(20))  # "ai" | "rule_based"
    ai_provider: Mapped[str | None] = mapped_column(String(40))
    ai_model: Mapped[str | None] = mapped_column(String(80))
    fallback_reason: Mapped[str | None] = mapped_column(String(120))

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class UserFile(Base):
    """Metadata for a file kept in object storage. The bytes live in the bucket under
    ``storage_path``; this row records who owns them and what they are."""

    __tablename__ = "user_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))  # sanitised display name only
    storage_path: Mapped[str] = mapped_column(String(512), unique=True)  # object key
    content_type: Mapped[str] = mapped_column(String(100))  # detected from the bytes
    size_bytes: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(30))  # meal_image | document | plan_export
    plan_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("diet_plans.id", ondelete="SET NULL"), index=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class RevokedToken(Base):
    """JWT IDs that were logged out before they expired (server-side logout)."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    revoked_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
