# 13 · Source code guide

The complete, runnable source is the repository itself. Every file listed in
[12 · Folder structure](12-folder-structure.md) is there in full, commented for beginners and
covered by tests. This chapter gives a **reading order** and the key idea in each file, so you
can explain any part in a viva or interview.

## Reading order (about two hours)

| # | File | What to notice |
|---|---|---|
| 1 | [`backend/config.py`](../backend/config.py) | Twelve-factor settings: every value from the environment, validated; production refuses a weak JWT secret; blank values count as "unset" |
| 2 | [`backend/app.py`](../backend/app.py) | `create_app()` wires config → database → storage → AI planner → middleware → routers. Tests call it with their own settings |
| 3 | [`backend/models/db_models.py`](../backend/models/db_models.py) | Four tables, UUID keys, `user_id` foreign keys, the `UTCDateTime` type |
| 4 | [`backend/models/schemas.py`](../backend/models/schemas.py) | The API contract: validation ranges, the password policy, response models that never include secrets |
| 5 | [`backend/utils/security.py`](../backend/utils/security.py) | bcrypt and JWT in about 100 lines |
| 6 | [`backend/utils/dependencies.py`](../backend/utils/dependencies.py) | `get_current_user`: the single gate every protected route passes through |
| 7 | [`backend/routes/plan_routes.py`](../backend/routes/plan_routes.py) → [`backend/services/plan_service.py`](../backend/services/plan_service.py) | Thin routes, rules in services, and every query filtered by `user_id` |
| 8 | [`ai_engine/nutrition.py`](../ai_engine/nutrition.py) → [`diet_engine.py`](../ai_engine/diet_engine.py) | Formulas, then filter → scale → score → pick |
| 9 | [`ai_engine/prompts.py`](../ai_engine/prompts.py) → [`llm_providers.py`](../ai_engine/llm_providers.py) → [`validation.py`](../ai_engine/validation.py) → [`planner.py`](../ai_engine/planner.py) | Safe LLM integration and the fallback |
| 10 | [`cloud/storage_service.py`](../cloud/storage_service.py) → [`backend/services/file_service.py`](../backend/services/file_service.py) | Adapter pattern; magic bytes; compensating delete |
| 11 | [`backend/utils/errors.py`](../backend/utils/errors.py) · [`middleware.py`](../backend/utils/middleware.py) | Consistent errors, 503 on outages, request IDs, security headers |
| 12 | [`frontend/src/services/apiClient.js`](../frontend/src/services/apiClient.js) → [`context/AuthContext.jsx`](../frontend/src/context/AuthContext.jsx) → [`pages/GeneratePlanPage.jsx`](../frontend/src/pages/GeneratePlanPage.jsx) | How the UI calls the API and handles the session |
| 13 | [`tests/test_isolation.py`](../tests/test_isolation.py), [`tests/test_ai_fallback.py`](../tests/test_ai_fallback.py) | How the two most important guarantees are proven |

## Five snippets worth memorising

**1. Configuration, not code, chooses the cloud** ([`backend/app.py`](../backend/app.py)):

```python
database = DatabaseService(settings.database_url, …)            # sqlite:///… or postgresql://…
storage = create_storage_service(settings.storage_provider, …)  # "local" or "s3"
```

**2. One gate for identity** ([`dependencies.py`](../backend/utils/dependencies.py)): routes
declare `user: CurrentUser` and never parse tokens themselves.

**3. Ownership in the query itself** ([`plan_service.py`](../backend/services/plan_service.py)):

```python
select(DietPlan).where(DietPlan.id == plan_id, DietPlan.user_id == user_id)
```

**4. AI with a safety net** ([`planner.py`](../ai_engine/planner.py)):

```python
try:
    return self._generate_with_ai(request, targets)
except (AIProviderError, AIValidationError) as exc:
    reason = exc.reason
plan = self.rule_engine.generate(request, targets)
return plan.model_copy(update={"fallback_reason": reason})
```

**5. No orphaned files** ([`file_service.py`](../backend/services/file_service.py)): upload
the object, then save metadata; if saving fails, delete the object again.

## Conventions used throughout

- **Layers:** routes (HTTP) → services (rules) → cloud adapters (providers). Nothing above
  `cloud/` imports boto3 or database drivers directly.
- **Errors:** services raise `AppError` subclasses (`NotFoundError`, `ConflictError` …), and
  one handler turns them into the JSON error shape. Unexpected exceptions become a generic
  500 that includes the request ID; stack traces stay in the logs.
- **Types:** Python type hints and Pydantic models everywhere; `StrEnum` for options.
- **Style:** `ruff` enforces formatting, import order, bug patterns and security rules (the
  `S` rules come from Bandit). CI fails on any finding.
- **Secrets:** read only through `Settings`; never logged or returned.
