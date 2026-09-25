# 17 · Cloud security

| Topic | What it means | How this project does it | Where |
|---|---|---|---|
| **Authentication** | Verifying identity | bcrypt password check → signed JWT; every protected request re-verifies the signature, expiry, type and revocation | [`security.py`](../backend/utils/security.py), [`dependencies.py`](../backend/utils/dependencies.py) |
| **Authorization** | Deciding access | The owner filter is in every query; other users' IDs give 404; no admin backdoor | [`plan_service.py`](../backend/services/plan_service.py), [`file_service.py`](../backend/services/file_service.py) |
| **Password security** | Resisting stolen-database attacks | bcrypt (12 rounds, salted, slow), 8+ characters with a letter and a digit, 72-byte cap, constant-time compare, never logged or returned | [`security.py`](../backend/utils/security.py), [`schemas.py`](../backend/models/schemas.py) |
| **HTTPS** | Encrypted, authenticated connections | Render, Vercel and ALB/ACM terminate TLS; `Strict-Transport-Security` is sent in production (`ENVIRONMENT=production`); uvicorn `--proxy-headers` | [`middleware.py`](../backend/utils/middleware.py), [`Dockerfile`](../Dockerfile) |
| **Encryption in transit** | Nobody on the network can read data | Browser ↔ app over HTTPS; app ↔ PostgreSQL with `sslmode=require`; app ↔ S3 and the AI API over HTTPS | [15 · Deployment](15-cloud-deployment.md) |
| **Encryption at rest** | Stolen disks are useless | Neon, Supabase, RDS (enable at creation), S3 (SSE-S3 by default), R2 and Supabase Storage all encrypt at rest; passwords are hashed, not encrypted | provider settings |
| **Environment variables** | Configuration outside the code | All settings come from the environment; `.env.example` documents them without values | [`config.py`](../backend/config.py), [`.env.example`](../.env.example) |
| **Secrets management** | Protect and rotate credentials | `.env` is gitignored and excluded from Docker images; Render generates the JWT key; `sync: false` secrets; AWS Secrets Manager; production refuses a weak JWT key; secrets never appear in `/api/system/status` or logs | [`.gitignore`](../.gitignore), [`.dockerignore`](../.dockerignore), [`render.yaml`](../render.yaml) |
| **API-key protection** | AI keys must not leak or be abused | Keys stay server-side, never reach the browser, never go in the repo; the per-user rate limit on plan generation caps spend; the app works without any key | [`llm_providers.py`](../ai_engine/llm_providers.py) |
| **Database access rules** | Least privilege at the data layer | The app only uses parameterised SQLAlchemy queries (no string SQL, so no SQL injection); RDS in private subnets reachable only from app tasks; a dedicated database user rather than the superuser in production | [06 · Database](06-database-design.md) |
| **Object-storage permissions** | Buckets must not be public | Private bucket, Block Public Access; no public URLs, since downloads go through the API after an ownership check; an IAM role limited to `users/*` in one bucket | [08 · Storage](08-cloud-storage.md), [15 · Deployment](15-cloud-deployment.md) |
| **Input validation** | Never trust the client | Pydantic schemas with ranges and enums; unknown enum values rejected (422); magic-byte file detection; sanitised filenames; server-generated object keys; the AI prompt built only from enums | [`schemas.py`](../backend/models/schemas.py), [`file_validation.py`](../backend/utils/file_validation.py) |
| **Rate limiting** | Slow brute force and abuse | Sliding window: 10 auth attempts/min per IP, 20 plan generations/min per user; 429 with `Retry-After`; `TRUST_PROXY_HEADERS` for the real client IP | [`rate_limiter.py`](../backend/utils/rate_limiter.py) |
| **CORS** | Which websites may call the API from a browser | An explicit allow-list (`CORS_ORIGINS`); credentials off (tokens use a header, not cookies); limited methods and headers | [`app.py`](../backend/app.py) |
| **Security headers** | Browser-side hardening | CSP (`default-src 'none'` for the API; `'self'`-only for the web app), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, `Cache-Control: no-store` on API responses | [`middleware.py`](../backend/utils/middleware.py) |
| **Logging** | Audit and debugging without leaking data | Structured logs with request IDs; registrations logged with the user ID only, failed logins without the email; auth events counted in `/api/metrics`; no passwords, tokens, request bodies or file contents | [`logging_config.py`](../backend/utils/logging_config.py) |
| **Backups** | Recover from mistakes and disasters | Managed point-in-time recovery (Neon, Supabase, RDS automated backups); S3 versioning (optional); code in Git; the schema recreated automatically | provider settings |
| **Container security** | Limit the blast radius | A slim base image, a non-root user (UID 10001), no secrets in layers, a `HEALTHCHECK` | [`Dockerfile`](../Dockerfile) |
| **Supply chain** | Trust your dependencies | A locked frontend dependency tree (`package-lock.json`, `npm ci`); pinned CI action versions; `ruff` security rules on every push | [CI](../.github/workflows/ci.yml) |

## Error handling that doesn't leak

- Unexpected exceptions return `{"error": {"code": "internal_error", "request_id": …}}`. The
  stack trace goes to the logs only.
- Database or storage outages return 503 with a friendly message, never the driver's error
  text, which could reveal hostnames.
- Login failures don't reveal whether an email exists.
- Another user's resource returns 404, which doesn't confirm that it exists.

## Common mistakes students should avoid

1. **Committing `.env`, API keys or cloud credentials.** Bots scan GitHub for leaked keys
   within minutes. If it happens, *rotate the key immediately*; deleting the commit is not
   enough.
2. **Storing plain-text or fast-hashed passwords** (MD5, SHA-256). Use bcrypt, scrypt or
   Argon2.
3. **Trusting a user ID from the request body or URL.** Take it from the verified token.
4. **Checking "is logged in" but not "owns this record"** (IDOR / broken object-level
   authorization, #1 in the OWASP API Top 10).
5. **Public buckets** "to make images load". Serve through the API or use short-lived
   presigned URLs.
6. **`allow_origins=["*"]` with credentials**, or CORS used as if it were authentication (it
   only restricts browsers).
7. **Hard-coded JWT secrets** such as `"secret"`, or `alg=none` accepted.
8. **Returning stack traces or SQL errors to users.**
9. **Validating only in the frontend.** Anyone can call the API with `curl`.
10. **Trusting file extensions or `Content-Type` from the client** for uploads.
11. **Logging tokens, passwords or full request bodies.**
12. **Sending personal data to an AI API unnecessarily**, or using an AI answer without
    checking it.
13. **Running containers as root**, and leaving default database passwords.
14. **No rate limiting on login.**

## Reporting

See [SECURITY.md](../SECURITY.md).
