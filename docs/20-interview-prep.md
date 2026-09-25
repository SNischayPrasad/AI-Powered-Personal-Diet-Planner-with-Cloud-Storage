# 20 · Interview preparation

## The 30-second pitch

> "I built an AI-powered diet planner as a cloud-native app. It has a React frontend and a
> stateless FastAPI backend. Structured data goes in PostgreSQL, and meal photos and plan
> exports go in S3-compatible object storage. Users get a personalised day of meals
> computed from their profile. An LLM can suggest dishes, but every answer is validated
> against the user's diet, allergens and calorie target, and if it fails it falls back
> automatically to my rule-based engine, so the app never breaks. The same Docker image
> runs locally, on Render's free tier or on AWS, switched purely by environment variables.
> There are 297 backend tests, including user-isolation and outage tests, and CI runs them
> on SQLite and PostgreSQL and smoke-tests the production container."

## The 2-minute walkthrough (whiteboard)

1. Draw browser → API → (database, object storage, AI provider).
2. Follow one request: *generate plan*. JWT check → the user's profile → targets →
   AI or rules → validate → save → render.
3. Name three design decisions: stateless auth, a separate DB vs object store, and AI with
   validation and fallback.
4. Two failure stories: the AI provider is down (a rule-based plan, with the reason
   recorded), and the database is down (readiness 503, degraded mode, auto-recovery).
5. How it scales: more instances behind a load balancer, pooling, CDN, Redis, a queue for
   AI.

## Cloud fundamentals

**Q: IaaS vs PaaS vs SaaS, using your project?**
IaaS is renting building blocks: in Approach B, VPC, subnets and security groups. PaaS runs
my code without me managing servers: Render, Vercel, Neon, RDS. SaaS is a finished product:
my app for its users, and the Claude API for me.

**Q: Why a database *and* object storage?**
They are built for different jobs. The database handles structured, queryable,
transactional data: who owns which plan, sorted by date. Object storage handles large,
cheap, durable blobs addressed by key. Putting images in the database bloats backups and
slows queries. Putting plans in a bucket loses querying and integrity. The `user_files`
row links the two.

**Q: What does "stateless" mean, and why does it matter?**
The server keeps no per-user memory between requests. Identity arrives in each request
(the JWT), and data lives in shared services. So any instance can serve any request:
horizontal scaling, rolling deploys and serverless all become possible. My one deliberate
exception is the in-memory rate limiter, which I'd move to Redis.

**Q: Scalability vs elasticity?**
Scalability is the *ability* to handle more load by adding resources. Elasticity is doing
it *automatically, in both directions*, as demand changes. That is where the cost savings
come from.

**Q: High availability here?**
Multiple instances across availability zones behind a load balancer. The readiness probe
takes an instance out of rotation if it loses the database. A Multi-AZ managed database. The
app starts even if the database is down and recovers on its own.

**Q: Liveness vs readiness?**
Liveness (`/api/health`) asks "is the process alive?"; if not, restart it. Readiness
(`/api/health/ready`) asks "can it serve traffic now?", checking the database and storage;
if not, stop routing to it, but don't restart it, because a restart wouldn't fix a database
outage.

**Q: How do you manage secrets?**
Never in code or Git. They are environment variables, loaded from a gitignored `.env`
locally and from the platform's secret store in the cloud (Render env vars, AWS Secrets
Manager). On AWS the app doesn't need S3 keys at all, because it uses an IAM role.
Production refuses to start with a weak JWT secret. Leaked keys get rotated.

**Q: What is CI/CD in your project?**
CI: every push runs lint (with security rules), 297 tests on Python 3.11 and 3.13, the full
suite on a real PostgreSQL, the frontend tests and build, an end-to-end smoke test, and a
Docker build that is smoke-tested alone and with PostgreSQL plus S3 storage. CD: Render
redeploys `main` automatically. On AWS I'd use GitHub OIDC to push to ECR and update ECS.

## Security

**Q: How do you store passwords?**
bcrypt with 12 rounds. It is salted and deliberately slow, so a leaked database is
expensive to crack. It is compared in constant time, and passwords are never logged or
returned. There is a 72-byte limit because bcrypt ignores anything beyond it.

**Q: Explain your JWT.**
A header, a payload (`sub`, `jti`, `iat`, `exp`, `type`) and an HMAC-SHA256 signature using a
server secret. Anyone can *read* the payload, so it contains no secrets. Nobody can *change*
it without the key. I reject `alg=none`, bad signatures, wrong types and expired tokens.

**Q: JWTs can't be revoked. How does your logout work?**
Each token has a unique `jti`. Logout stores it in `revoked_tokens` until it would have
expired, and authentication checks that table. It is a small, deliberate bit of state. At
scale I'd put it in Redis with a TTL, or use short-lived access tokens plus refresh tokens.

**Q: How do you stop user A seeing user B's data?**
The user ID comes only from the verified token, and every query includes
`WHERE user_id = :me`. Someone else's ID returns 404, not 403, so existence isn't revealed.
IDs are random UUIDs. Eleven tests prove it across seven endpoints, and a mutation test
showed they fail if the filter is removed.

**Q: Why store the token in localStorage, not a cookie?**
With a header token there's no CSRF risk, and the API works for any client. The trade-off
is XSS exposure, which I mitigate with React's escaping and a strict CSP
(`script-src 'self'`). An httpOnly SameSite cookie is the other valid design; it would then
need CSRF protection.

**Q: How do you validate file uploads?**
By content, not name: magic bytes for JPEG, PNG, WebP and PDF. SVG and HTML are rejected.
There are size limits and quotas, the server generates the storage key (no path traversal),
the bucket is private, and downloads go through an ownership check.

**Q: What is CORS, and is it security?**
It is a browser rule about which origins may read responses from my API. It protects users'
browsers, not my server: `curl` ignores it. Real protection is authentication and
authorization. I use an explicit allow-list and no credentials.

## AI

**Q: How does the AI part work, and is it "real AI"?**
Two engines. The rule-based one is a knowledge-based recommender: a curated dataset plus
filtering, portion scaling and scoring. It is transparent, free and offline. The optional
LLM gets only enumerated preferences and computed targets, returns schema-constrained JSON,
and passes six validation checks before use. The numbers come from formulas, and the LLM
only proposes dishes.

**Q: How do you handle LLM failure or hallucination?**
I treat the LLM as an unreliable dependency. Timeouts, rate limits, auth errors, refusals,
truncation and invalid JSON all raise a typed error. The validator catches diet and allergen
violations and implausible nutrition. Any failure triggers the rule-based fallback, the plan
records `fallback_reason`, a metric counts it, and the user still gets a 201.

**Q: Prompt injection?**
Users never supply free text to the prompt, only values from fixed enums. Even if a model
misbehaved, its output is data I validate, never instructions I execute.

**Q: Privacy with the AI provider?**
Data minimisation: no name, email, age, height or weight is sent. Only diet, goal, cuisine,
allergens and computed calorie budgets. The key stays server-side.

## Design and trade-offs

**Q: Why FastAPI over Flask?**
Type-driven validation with Pydantic, automatic OpenAPI docs, dependency injection (great for
testing), and async support. Flask would work too, with more manual validation.

**Q: Why store meals as JSON in PostgreSQL?**
Meals are always read with their plan and have nested details. JSON avoids four joins while
plans stay relational. On PostgreSQL it could become JSONB with GIN indexes if we ever query
inside meals.

**Q: What would you change for production?**
Alembic migrations, Redis for rate limits and revocation, refresh tokens or a managed IdP,
presigned URLs and a CDN for files, a queue and worker for AI calls, OpenTelemetry tracing,
Terraform, and a WAF.

**Q: A bug you found and fixed?**
Some examples from this project:
- An AI test fixture whose dish descriptions contradicted swapped dish names, caught by the
  validator's tests.
- A registration redirect race between route guards.
- Blank environment values arriving as empty strings instead of "unset".
- Metrics recording the wrong route label, because of how this FastAPI version includes
  prefixed routers.
- The MinIO images being removed from Docker Hub, which broke the local cloud; I switched to
  RustFS and the AWS CLI image, and CI caught it.

**Q: How did you test failure handling?**
By injecting *real* failures rather than mocks. I placed a file where the database or bucket
directory should be, so the real driver or filesystem raises. Then I asserted a 503, the
readiness response, that no orphaned objects were left, and automatic recovery.

## Numbers to remember

| | |
|---|---|
| Backend tests / coverage | 297 / 97% |
| Frontend tests | 31 |
| Smoke checks | 28 |
| CI jobs | 6 (Python 3.11 + 3.13, PostgreSQL, frontend, smoke, Docker full stack) |
| Dishes in the dataset | 65 |
| AI validation checks | 6; day total within ±20% |
| Calorie floor / ceiling | 1,200 / 4,000 kcal |
| bcrypt rounds / JWT lifetime | 12 / 60 minutes |
| Upload limit / quota | 4 MB / 50 files per user |
| Rate limits | 10 auth attempts/min per IP, 20 plans/min per user |

## Viva checklist

- [ ] Can you demo it locally in under 2 minutes (API + frontend, register → plan → upload)?
- [ ] Can you show the plan in the database *and* the file in the bucket (step 15 of
      [14 · Local setup](14-local-setup.md))?
- [ ] Can you trigger the fallback live? Set `AI_PROVIDER=openai_compatible` with an
      unreachable `OPENAI_COMPAT_BASE_URL`, restart, generate, and show the badge.
- [ ] Can you show the TC-18 isolation tests passing (`pytest -k tc18`)?
- [ ] Can you explain every line of `render.yaml` and the `Dockerfile`?
