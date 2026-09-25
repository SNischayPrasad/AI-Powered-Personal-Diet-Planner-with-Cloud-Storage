# 05 · System architecture

## Layers

| Layer | Component | Technology | Responsibility |
|---|---|---|---|
| Client | Web browser | Any modern browser | Renders the UI; stores only the access token |
| Client | Frontend | React 19 SPA ([`frontend/`](../frontend)) | Pages, forms, client-side validation, API calls |
| Application | REST API | FastAPI ([`backend/routes/`](../backend/routes)) | HTTP contract, auth dependency, status codes |
| Application | Services | [`backend/services/`](../backend/services) | Business rules: profiles, plans, files, exports |
| AI | Diet recommendation engine | [`ai_engine/`](../ai_engine) | Targets, rule engine, LLM providers, validation, fallback |
| Data | Cloud database | SQLAlchemy → SQLite / PostgreSQL ([`cloud/database_service.py`](../cloud/database_service.py)) | Users, profiles, plans, file metadata, revoked tokens |
| Storage | Cloud object storage | Local folder / S3 API ([`cloud/storage_service.py`](../cloud/storage_service.py)) | Meal images, PDFs, plan exports |
| Auth | Authentication service | bcrypt + JWT ([`backend/utils/security.py`](../backend/utils/security.py)) | Identity, token issue, verify and revoke |

## Architecture diagram

```text
                                   User
                                    ↓
                     Frontend (React SPA, HTTPS)
                                    ↓   Authorization: Bearer <JWT>
          Authentication (verify signature · expiry · not revoked)
                                    ↓
                    REST API  /api/*  (FastAPI routers)
     middleware: request ID · security headers · CORS · metrics · rate limits
                                    ↓
                 Backend application (services layer)
          ┌─────────────────────────┼───────────────────────────┐
          ↓                         ↓                           ↓
     AI engine                 Cloud database              Cloud storage
  targets → LLM (opt.)      users · diet_plans ·         users/<id>/meal-images/…
  → validate → fallback     user_files ·                 users/<id>/plan-exports/…
  → rule-based engine       revoked_tokens               (private bucket)
          ↓                         ↑                           ↑
      Diet plan ──── saved ─────────┘      exports / uploads ───┘
          ↓
      Dashboard (latest plan, history, files, cloud status)
```

## Backend structure: routes → services → cloud adapters

```text
backend/routes/plan_routes.py      HTTP: parse and validate, call a service, map to a status code
   ↓
backend/services/plan_service.py   rules: load the user's profile, apply overrides, call the planner, save
   ↓                    ↓
ai_engine/planner.py    cloud/database_service.py · cloud/storage_service.py   (swappable adapters)
```

- **Dependency injection** ([`backend/utils/dependencies.py`](../backend/utils/dependencies.py)):
  routes receive `CurrentUser`, `DbSession`, `Storage`, `AppSettings` and `AppMetrics`.
  Tests build the app with their own settings, so every test gets an isolated database and
  bucket.
- **Adapters** hide the provider. `StorageService` has `LocalStorageService` and
  `S3StorageService`, and `DatabaseService` accepts any SQLAlchemy URL. Moving from the
  laptop to the cloud is configuration only.
- **Application factory** ([`backend/app.py`](../backend/app.py)): `create_app(settings)`
  wires configuration, database, storage, planner, middleware, error handlers and routers.
  When `FRONTEND_DIST_DIR` is set it also serves the React build
  ([`backend/utils/spa.py`](../backend/utils/spa.py)).

## Complete data flow: "Generate a plan"

1. **Browser**: the user presses *Generate*. React sends `POST /api/generate-plan` with
   optional one-off overrides and the JWT in the `Authorization` header.
2. **Middleware** assigns a request ID, and the rate limiter checks this client's recent
   requests (429 if over the limit).
3. **Auth dependency** decodes the JWT. It verifies the HMAC-SHA256 signature, the expiry,
   `type=access`, and that the `jti` is not revoked, then loads the user. Any failure gives
   401.
4. **Plan service** checks the profile is complete (otherwise 400 `profile_incomplete`) and
   merges the overrides into a `PlanRequest`. That object holds only enumerated values and
   numbers: no name, no email.
5. **Nutrition maths** computes BMR, TDEE, the calorie target, macro targets, per-meal
   budgets and water.
6. **AI planner**: if an LLM is configured and enabled, it sends a structured prompt, parses
   the JSON answer and validates it. Otherwise, or on any error or rejection, the rule-based
   engine builds the plan and the reason is recorded.
7. **Database**: the plan is inserted into `diet_plans` with `user_id`, a preferences
   snapshot, meals, summary and provenance. The response is 201 with the plan.
8. **Browser** navigates to `/plans/<id>` and renders the thali, macro meters and meal
   cards.
9. **Optional storage**: *Save to cloud* stores a JSON or text export at
   `users/<id>/plan-exports/<uuid>.txt` and records a `user_files` row. Uploads follow the
   same path to `meal-images/` or `documents/`.
10. **Observability**: the request is logged with its ID, and counters record the request,
    the engine used and any AI fallback.

## Deployment topologies (same code)

| Topology | Frontend | API | Data |
|---|---|---|---|
| Local development | Vite dev server `:5173` (proxies `/api`) | `uvicorn --reload` `:8000` | SQLite + folder |
| Local cloud simulation | Vite | uvicorn | PostgreSQL + RustFS (S3) in Docker |
| Single container | Served by FastAPI | Docker image | Neon/Supabase + S3-compatible |
| Split | Vercel CDN | Render | Neon/Supabase + S3-compatible |
| Serverless | Vercel static | Vercel Python function | Neon/Supabase + S3-compatible |
| AWS | Container (+ CloudFront) | ECS Fargate behind ALB | RDS + S3 |

## Why these decisions

| Decision | Reason |
|---|---|
| Stateless JWT auth | Any instance can serve any request, which enables horizontal scaling and serverless |
| Separate database and object store | Each is used for what it does best: queries vs. cheap durable files |
| UUID keys everywhere | Not guessable; generated anywhere without coordination |
| Rule engine always available | The product works with no paid API and survives AI outages |
| Serve the SPA from the API | One origin: no CORS setup and a strict CSP; one service to deploy |
| Readiness separate from liveness | Load balancers stop routing to an instance that lost its database without restarting it |
