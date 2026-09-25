# 06 · Database design

Defined as SQLAlchemy models in [`backend/models/db_models.py`](../backend/models/db_models.py).
The same schema runs on SQLite (local) and PostgreSQL (cloud).

## Entity-relationship diagram

```text
┌──────────────────────────┐        ┌──────────────────────────────┐
│ users                    │        │ diet_plans                   │
├──────────────────────────┤        ├──────────────────────────────┤
│ id            PK uuid    │◄──┐    │ id               PK uuid     │
│ name                     │   ├────│ user_id          FK → users  │
│ email         UNIQUE     │   │    │ title                        │
│ password_hash (bcrypt)   │   │    │ dietary_preference, goal,    │
│ age, sex                 │   │    │ cuisine, allergies (snapshot)│
│ height_cm, weight_kg     │   │    │ calorie_target               │
│ activity_level           │   │    │ breakfast, lunch, snack,     │
│ dietary_preference       │   │    │ dinner            JSON       │
│ goal                     │   │    │ nutrition_summary JSON       │
│ allergies     JSON       │   │    │ hydration_tip, tips, disclaimer
│ cuisine_preference       │   │    │ source, ai_provider,         │
│ created_at, updated_at   │   │    │ ai_model, fallback_reason    │
└──────────────────────────┘   │    │ created_at                   │
                               │    └──────────────┬───────────────┘
┌──────────────────────────┐   │                   │ 0..1
│ revoked_tokens           │   │    ┌──────────────▼───────────────┐
├──────────────────────────┤   │    │ user_files                   │
│ jti           PK         │   │    ├──────────────────────────────┤
│ user_id       FK → users │───┤    │ id               PK uuid     │
│ expires_at, revoked_at   │   └────│ user_id          FK → users  │
└──────────────────────────┘        │ filename (sanitised)         │
                                    │ storage_path UNIQUE (obj key)│
                                    │ content_type, size_bytes     │
                                    │ category                     │
                                    │ plan_id    FK → diet_plans   │
                                    │ uploaded_at                  │
                                    └──────────────────────────────┘
```

## Tables vs. the brief

| Brief | Table / columns | Notes |
|---|---|---|
| USERS: user_id, name, email, age, height, weight, activity_level, dietary_preference, goal, created_at | `users`: `id`, `name`, `email`, `age`, `height_cm`, `weight_kg`, `activity_level`, `dietary_preference`, `goal`, `created_at` | Plus `password_hash`, `sex`, `allergies`, `cuisine_preference`, `updated_at` |
| DIET_PLANS: plan_id, user_id, breakfast, lunch, snack, dinner, nutrition_summary, created_at | `diet_plans`: `id`, `user_id`, `breakfast`, `lunch`, `snack`, `dinner`, `nutrition_summary`, `created_at` | Plus a preferences snapshot, calorie target, hydration, tips, disclaimer, provenance |
| USER_FILES: file_id, user_id, filename, storage_path, uploaded_at | `user_files`: `id`, `user_id`, `filename`, `storage_path`, `uploaded_at` | Plus `content_type`, `size_bytes`, `category`, `plan_id` |
| – | `revoked_tokens` | Server-side logout |

## Primary keys

Every table uses a **UUID** (`String(36)`) primary key, except `revoked_tokens`, which is
keyed by the token's unique `jti`.

- **Not guessable.** `/plans/1`, `/plans/2`… would invite enumeration. A UUID has 122
  random bits. This is defence in depth: authorization is still checked on every request.
- **Generated anywhere.** No database round trip or sequence coordination is needed, which
  helps with distributed systems and offline creation.
- **Portable.** Stored as text, so they work the same on SQLite and PostgreSQL.

## Relationships

| Relationship | Type | On delete |
|---|---|---|
| users 1 → N diet_plans | `diet_plans.user_id` FK | CASCADE: deleting a user deletes their plans |
| users 1 → N user_files | `user_files.user_id` FK | CASCADE |
| users 1 → N revoked_tokens | `revoked_tokens.user_id` FK | CASCADE |
| diet_plans 1 → 0..N user_files (exports) | `user_files.plan_id` FK, nullable | SET NULL: the exported file stays if the plan is deleted |

SQLite enforces foreign keys only when asked. The database service turns on
`PRAGMA foreign_keys=ON` for every connection.

## Cloud database design choices

- **Meals as JSON documents** inside a relational row. A meal has nested details
  (ingredients, macros, reasoning) that are always read together with the plan. JSON avoids
  a `meals` table and four joins per read, while plans stay relational (owner, time, filters).
  On PostgreSQL this maps to `JSON`, so it could later become `JSONB` with indexes.
- **Snapshot of preferences on each plan.** The profile can change later; the plan records
  the preferences it was made with.
- **Composite index `(user_id, created_at)`** serves the most common query, "my plans,
  newest first", without a sort.
- **UTC timestamps with a custom `UTCDateTime` type**, so SQLite (which stores naive
  datetimes) and PostgreSQL both return timezone-aware UTC values.
- **Unique `storage_path`**: each object belongs to exactly one metadata row.
- **Connection pooling.** PostgreSQL uses a bounded pool (`DB_POOL_SIZE` +
  `DB_MAX_OVERFLOW`), `pool_pre_ping` and `pool_recycle=300`. Connections that cloud load
  balancers silently drop are replaced instead of failing requests.
- **Resilient start-up.** If the database is down at boot, the app still starts, readiness
  reports `degraded`, and tables are created as soon as it's reachable.
- **Migrations.** Tables are created with `create_all` for simplicity. A production system
  would use Alembic migrations (listed under future improvements).

## User-specific access

Every query for user-owned data filters by the authenticated user's ID, which comes from the
verified token and never from the request body. For example, in
[`plan_service.py`](../backend/services/plan_service.py):

```python
select(DietPlan).where(DietPlan.id == plan_id, DietPlan.user_id == user_id)
```

If the row isn't found (it doesn't exist, or it belongs to someone else) the API returns
**404**. It never returns 403, which would confirm the ID exists. Test group **TC-18**
checks this across 7 endpoints. Removing the `user_id` filter makes 9 of its 11 tests fail
(a mutation check).

## Inspecting the data

```bash
# Local SQLite (Python ships with sqlite3)
python -c "import sqlite3; c=sqlite3.connect('data/diet_planner.db'); print(c.execute('select email, dietary_preference, goal from users').fetchall())"

# PostgreSQL (Docker)
docker compose exec postgres psql -U dietplanner -c "select title, source, created_at from diet_plans order by created_at desc limit 5;"
```
