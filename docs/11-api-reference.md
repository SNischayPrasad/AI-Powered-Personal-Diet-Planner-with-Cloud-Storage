# 11 · REST API reference

- **Base path** `/api`. The live, interactive reference is at `/api/docs` (Swagger UI) and
  `/api/redoc`, generated from the code, with the machine-readable spec at
  `/api/openapi.json`.
- **Format**: JSON in and out, except uploads (multipart) and downloads (file bytes).
- **Auth**: `Authorization: Bearer <access_token>` on every endpoint marked ✔.

## Conventions

| Status | Meaning here |
|---|---|
| 200 OK | Read or update succeeded |
| 201 Created | Account, plan or file created |
| 204 No Content | Deleted |
| 400 Bad Request | Well-formed but not allowed now, e.g. `profile_incomplete`, a file name that doesn't match its content |
| 401 Unauthorized | Missing, invalid, expired or revoked token; wrong login (`invalid_credentials`). Sent with `WWW-Authenticate: Bearer` |
| 403 Forbidden | Storage quota reached (`storage_quota_exceeded`) |
| 404 Not Found | Doesn't exist, **or belongs to another user** (deliberately indistinguishable) |
| 409 Conflict | Email already registered |
| 413 Payload Too Large | Upload over `MAX_UPLOAD_MB` |
| 415 Unsupported Media Type | Not a JPEG/PNG/WebP/PDF by content |
| 422 Unprocessable Entity | Validation failed (field-level details included) |
| 429 Too Many Requests | Rate limit hit, with `Retry-After` seconds |
| 503 Service Unavailable | Database or storage temporarily unreachable (`database_unavailable`, `storage_unavailable`) |

Every error has the same shape. The `request_id` is also in the `X-Request-ID` header and the
server logs:

```json
{"error": {"code": "not_found", "message": "Plan not found.", "request_id": "5b0c9e7a2f3d4c1e"}}
```

## Authentication

### `POST /api/register`
```json
{"name": "Asha Demo", "email": "asha.demo@example.com", "password": "Demo-password-1"}
```
→ **201**
```json
{"access_token": "eyJhbGciOiJIUzI1NiIs…", "token_type": "bearer", "expires_in": 3600,
 "user": {"id": "3f2c…", "name": "Asha Demo", "email": "asha.demo@example.com", "profile_complete": false, "…": "…"}}
```
Errors: 409 `email_already_registered`, 422 (weak password, bad email), 429.

### `POST /api/login`
`{"email", "password"}` → **200**, same body as register. Errors: 401 `invalid_credentials`
(the same for an unknown email and a wrong password), 429.

### `POST /api/logout` ✔
→ **200** `{"message": "You have been logged out."}`. The token is revoked immediately. Reusing it gives
401 `token_revoked`.

## Profile

### `GET /api/profile` ✔
→ **200** the user's profile (`profile_complete` tells the UI whether a plan can be
generated).

### `PUT /api/profile` ✔
```json
{"name": "Asha Demo", "age": 29, "sex": "female", "height_cm": 162, "weight_kg": 58,
 "activity_level": "lightly_active", "dietary_preference": "vegetarian", "goal": "balanced",
 "allergies": ["peanuts"], "cuisine_preference": "indian"}
```
Required: `age` (18–90), `height_cm` (100–250), `weight_kg` (30–300), `activity_level`,
`dietary_preference`, `goal`. Optional: `name`, `sex`, `allergies`, `cuisine_preference`.
Enumerated values are listed in [02 · Features](02-features.md). → **200**, or **422** with
field details.

## Diet plans

### `POST /api/generate-plan` ✔
All fields are optional one-off overrides. Anything left out comes from the profile.
```json
{"dietary_preference": "vegan", "goal": "fitness", "allergies": ["soy"], "cuisine_preference": "any", "use_ai": true}
```
→ **201**
```json
{
  "id": "cdd2c4f4-…", "title": "Vegan · Fitness-oriented demo · 2,270 kcal/day",
  "dietary_preference": "vegan", "goal": "fitness", "calorie_target": 2270,
  "breakfast": {"name": "…", "portion": "…", "ingredients": ["…"], "calories": 560,
                "protein_g": 28, "carbs_g": 70, "fat_g": 18, "fiber_g": 9, "why": "…"},
  "lunch": {"…": "…"}, "snack": {"…": "…"}, "dinner": {"…": "…"},
  "nutrition_summary": {"targets": {"…": "…"}, "totals": {"…": "…"}, "macro_percentages": {"…": "…"}},
  "hydration_tip": "Aim for roughly 2.3 L …", "tips": ["…"],
  "disclaimer": "Educational, general-wellness example …",
  "source": "rule_based", "ai_provider": null, "ai_model": null, "fallback_reason": null,
  "created_at": "2026-09-25T10:30:00Z"
}
```
Errors: 400 `profile_incomplete`, 422, 429. An AI failure is **not** an error: the plan
comes from the rules and `fallback_reason` says why. Full examples:
[`sample_data/exports/`](../sample_data/exports).

### `GET /api/plans?limit=20&offset=0` ✔
→ **200** `{"items": [PlanSummary…], "total": 3, "limit": 20, "offset": 0}`, newest first.

### `GET /api/plans/{plan_id}` ✔ · `DELETE /api/plans/{plan_id}` ✔
→ **200** the plan · **204**. Other users' or unknown IDs → **404**.

### `GET /api/plans/{plan_id}/export?format=json|txt` ✔
→ **200** a file download (`Content-Disposition: attachment`).

### `POST /api/plans/{plan_id}/save-to-cloud?format=json|txt` ✔
→ **201** the stored file's metadata (category `plan_export`). Errors: 403 quota, 404,
503 storage.

## Files (object storage)

### `POST /api/upload` ✔ (multipart/form-data, field `file`)
```bash
curl -H "Authorization: Bearer $TOKEN" -F "file=@sample_data/images/lunch-thali.png" http://localhost:8000/api/upload
```
→ **201**
```json
{"id": "9a1e…", "filename": "lunch-thali.png", "content_type": "image/png", "size_bytes": 190312,
 "category": "meal_image", "plan_id": null, "uploaded_at": "2026-09-25T10:31:00Z"}
```
Errors: 400 (empty, or the name contradicts the content), 403 quota, 413 too large, 415
unsupported type, 503 storage.

### `GET /api/files` ✔
→ **200** `{"items": [FileOut…], "total": 2, "total_bytes": 381204, "max_files": 50, "max_upload_mb": 4.0}`

### `GET /api/files/{file_id}/download` ✔ · `DELETE /api/files/{file_id}` ✔
→ **200** the bytes, with their detected content type · **204** (the object is deleted, then
the metadata row).

## Operations (no auth)

| Endpoint | Returns |
|---|---|
| `GET /api/health` | 200 `{"status": "ok", "service": "AI Diet Planner", "version": "1.0.0"}`: the process is alive (liveness) |
| `GET /api/health/ready` | 200 `{"status": "ready", "checks": {"database": "ok", "storage": "ok"}}`, or 503 with `"degraded"` and the failing check marked `"unavailable"` (readiness) |
| `GET /api/system/status` | Providers in use: `database_provider`, `storage_provider`, `ai_provider`, `ai_available`, `ai_model`, `max_upload_mb`, app name, version and environment. No secrets |
| `GET /api/metrics` | Prometheus text: `http_requests_total{method,route,status}`, `auth_events_total`, `plans_generated_total{source}`, `ai_fallbacks_total{reason}`, `files_uploaded_total`, `dependency_errors_total` (when `METRICS_ENABLED=true`) |

## Mapping to the brief

| Brief | Implemented as |
|---|---|
| `POST /register`, `POST /login` | `POST /api/register`, `POST /api/login` (+ `POST /api/logout`) |
| `GET /profile`, `PUT /profile` | same, under `/api` |
| `POST /generate-plan` | same, with optional overrides |
| `GET /plans`, `GET /plans/{id}`, `DELETE /plans/{id}` | same, plus export and save-to-cloud |
| `POST /upload`, `GET /files`, `DELETE /files/{id}` | same, plus download |
