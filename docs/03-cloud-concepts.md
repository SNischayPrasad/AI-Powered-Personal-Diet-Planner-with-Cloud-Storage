# 03 · Cloud computing concepts, and where each one lives in this project

| Concept | Meaning in one line | Where it is in this project |
|---|---|---|
| **Cloud computing** | On-demand computing resources over the internet, paid by use | The app runs on hosted compute (Render / Vercel / AWS) and uses managed database, storage and AI services |
| **SaaS** | Software delivered as a finished service | The diet planner itself: users need only a browser and an account. The Claude / Gemini APIs we call are SaaS too |
| **PaaS** | The platform runs your code; you don't manage servers or OSes | Render builds the [`Dockerfile`](../Dockerfile) from [`render.yaml`](../render.yaml); Vercel runs [`api/index.py`](../api/index.py); Neon / Supabase run PostgreSQL |
| **IaaS** | Rent raw building blocks: networks, VMs, disks | Approach B in [15 · Deployment](15-cloud-deployment.md): VPC, subnets, security groups, load balancer, Fargate tasks |
| **Cloud storage** | Storing data on provider-managed, replicated infrastructure | Both the database and the bucket live with the provider; nothing important stays on the app server |
| **Cloud database** | A managed database with backups, patching and scaling handled by the provider | `DATABASE_URL` → PostgreSQL ([`cloud/database_service.py`](../cloud/database_service.py)); SQLite locally |
| **Object storage** | Flat key → bytes store for files, accessed over HTTP (S3 API) | [`cloud/storage_service.py`](../cloud/storage_service.py): local folder or S3 / Supabase Storage / R2 / RustFS; keys like `users/<id>/meal-images/<uuid>.png` |
| **Authentication** | Proving who you are | bcrypt + JWT in [`backend/utils/security.py`](../backend/utils/security.py) and [`auth_service.py`](../backend/services/auth_service.py) |
| **REST API** | Resources and HTTP verbs, stateless requests, JSON | [`backend/routes/`](../backend/routes): `POST /api/generate-plan`, `GET /api/plans/{id}`, `DELETE /api/files/{id}` … |
| **Client-server architecture** | Thin client asks, server decides and stores | The React app has no business logic or secrets; the API enforces every rule |
| **Serverless computing** | Code runs per request; the platform scales instances, even to zero | Vercel Python function ([`vercel.json`](../vercel.json)); the stateless design makes this possible |
| **Scalability** | Handling more load by adding resources | Stateless API (JWT, no server sessions) → add instances; a bounded DB connection pool per instance ([18 · Scalability](18-scalability.md)) |
| **Availability** | The service keeps answering despite failures | `/api/health/ready` for load-balancer checks; degraded mode on database outage; 2 tasks across 2 AZs on AWS; auto-recovery when the database returns |
| **Elasticity** | Scaling out *and in* automatically with demand | ECS target tracking (60% CPU, 2–6 tasks); serverless instances; free tier sleeping when idle |
| **Load balancing** | Spreading requests across healthy instances | Render / Vercel edge proxies; AWS ALB with health checks; `TRUST_PROXY_HEADERS` for real client IPs |
| **API gateway** | One managed entry point for APIs: routing, TLS, throttling | Everything is under `/api`; the platform edge (or ALB / API Gateway on AWS) terminates TLS; the app adds rate limits, CORS and request IDs |
| **Environment variables** | Configuration outside the code (twelve-factor) | [`backend/config.py`](../backend/config.py) reads every setting from the environment; [`.env.example`](../.env.example) documents them |
| **Secrets management** | Keeping credentials out of code and repos | `.env` is gitignored; Render `generateValue` for the JWT key; `sync: false` secrets; AWS Secrets Manager + IAM roles (no S3 keys at all) |
| **Cloud security** | Shared responsibility: the provider secures infrastructure, we secure the app and configuration | Private buckets, TLS, least-privilege IAM policy, security headers, non-root container, input validation ([17 · Security](17-security.md)) |
| **Logging** | Recording events for debugging and audit | Structured logs ([`logging_config.py`](../backend/utils/logging_config.py)); `LOG_FORMAT=json` for CloudWatch / Render; each line carries a `request_id` |
| **Monitoring** | Measuring health and behaviour over time | `/api/metrics` (Prometheus text): request counts by route and status, AI fallbacks, dependency errors; readiness probe; CloudWatch alarms in Approach B |
| **Deployment** | Getting a build running in the target environment | A multi-stage Docker image; Render Blueprint; Vercel config; ECS rolling deployments with health checks |
| **CI/CD** | Automated build and test on every change; automated release | [GitHub Actions](../.github/workflows/ci.yml): lint, tests on SQLite + PostgreSQL, frontend build, smoke test, Docker full-stack test. Render auto-deploys `main` |

## The shared responsibility model, applied

| The cloud provider secures | We secure |
|---|---|
| Data centres, hardware, hypervisor, managed-service patching, storage durability | Our code, dependencies, IAM permissions, bucket privacy, secrets, input validation, user isolation, what we log |

## Service models in the stack

```text
SaaS   ─ the diet planner (for users)          · Claude / Gemini APIs (for us)
PaaS   ─ Render, Vercel, Neon, Supabase         · AWS RDS, ECS Fargate (managed containers)
IaaS   ─ AWS VPC, subnets, security groups, load balancer (Approach B)
```
