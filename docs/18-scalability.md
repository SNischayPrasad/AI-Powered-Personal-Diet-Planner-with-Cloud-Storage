# 18 · Scalability

## What makes this app scalable already

- **Stateless API.** Identity lives in the JWT and data lives in managed services. Any
  instance can answer any request, so you scale by adding instances.
- **Separate data services.** Database and object storage scale independently of the app.
- **Bounded resources per instance.** A fixed database connection pool, upload size caps,
  per-user quotas and rate limits.
- **Health checks** so load balancers route only to ready instances.
- **Static frontend.** Fingerprinted assets are cached for a year, so they are ideal for a
  CDN.

## What happens at…

### 10 users (class demo)

One small instance (Render free tier or a laptop) and SQLite or a free PostgreSQL. Requests
take milliseconds; plan generation with rules takes under 50 ms, and an LLM call takes a few
seconds. Nothing to change. The only noticeable effect is the free tier's cold start after
it sleeps.

### 1,000 users (a college)

Peaks might be 20–50 requests per second at lunchtime.

- **App**: 2–3 instances behind the platform load balancer, for availability more than
  capacity. Turn off sleeping (paid tier), with health checks on `/api/health/ready`.
- **Database**: managed PostgreSQL (Neon, Supabase or RDS `db.t4g.small`), using the pooled
  connection string. Watch `instances × (DB_POOL_SIZE + DB_MAX_OVERFLOW)` against the
  database's connection limit. The `(user_id, created_at)` index keeps "my plans" fast.
- **Storage**: already fine. Object stores scale virtually without limit.
- **Rate limiter**: currently in memory per instance, so limits multiply by the instance
  count. Move it to **Redis** (a shared counter).
- **AI**: provider rate limits start to matter. Keep the rule-based fallback, and consider
  caching.

### 100,000 users (a national app)

Peaks might be thousands of requests per second, with millions of plans and terabytes of
images.

| Concern | Change |
|---|---|
| Compute | Auto-scaled containers (ECS/Fargate, Cloud Run) across 2–3 availability zones; scale on CPU and request count; or serverless functions for spiky traffic |
| Static content | Frontend and images through a **CDN** (CloudFront, Cloudflare); presigned URLs for direct browser ↔ S3 uploads and downloads, so file bytes skip the API |
| Database | Larger primary + **read replicas** for list and history reads; **PgBouncer / RDS Proxy** for connection pooling; partition or archive old `diet_plans`; move tokens to Redis with a TTL |
| Caching | **Redis / ElastiCache**: rate limits, the revoked-token set (TTL = token expiry), the food dataset, and cached plans for common preference combinations |
| Slow work | **Queue** (SQS / Pub/Sub) + workers for AI generation: the API returns `202 Accepted` with a job ID, the client polls or gets a WebSocket push, retries use backoff, and failed jobs go to a dead-letter queue |
| AI cost | Cache by preference combination, use cheaper models or low effort, keep the per-user quotas; the rule engine absorbs overflow |
| Observability | Centralised logs, metrics dashboards, tracing (OpenTelemetry), alarms on the 5xx rate, latency and the AI fallback rate |
| Security at scale | WAF in front of the load balancer; managed identity provider (Cognito / Auth0) with short-lived tokens and refresh tokens |
| Multi-region (optional) | Aurora Global Database or regional read replicas, a Route 53 latency-based routing policy, S3 cross-region replication |

## The scaling toolbox, mapped

| Technique | What it does | In this project |
|---|---|---|
| **Autoscaling** | Adds or removes instances with load (elasticity) | ECS target tracking at 60% CPU, 2–6 tasks ([15](15-cloud-deployment.md)); serverless on Vercel |
| **Load balancers** | Spread traffic, remove unhealthy instances | Render / Vercel edge, AWS ALB using `/api/health/ready` |
| **Serverless functions** | Per-request compute, scale to zero, pay per use | [`api/index.py`](../api/index.py) on Vercel; possible for AI workers (Lambda) |
| **Managed databases** | The provider handles replication, backups, failover and vertical scaling | Neon / Supabase / RDS; Multi-AZ; read replicas at scale |
| **CDN** | Serve static files from edge locations near users | Immutable `/assets/*` caching; CloudFront or Vercel CDN |
| **Caching** | Avoid repeating expensive work | HTTP caching for assets; Redis for rate limits, sessions and plan caching (future) |
| **Object storage** | Unlimited, durable file storage decoupled from servers | S3 / Supabase Storage / R2; presigned URLs at scale |
| **Queues** | Absorb spikes, decouple slow tasks, retry safely | SQS + workers for AI generation (future) |

## Bottlenecks, in the order you'd hit them

1. **Database connections** (fix with pooling or a proxy) come before CPU.
2. **AI provider rate limits and latency** (fix with a queue, caching and the fallback).
3. **Per-instance rate limiter** (fix with Redis).
4. **File bytes flowing through the API** (fix with presigned URLs and a CDN).
5. **The single primary database for writes** (fix with read replicas, partitioning and, much
   later, sharding by user ID).

## Interview soundbites

- "Stateless services scale horizontally; state goes into managed stores built to scale."
- "Scale reads with replicas and caches. Scale writes with partitioning, and keep hot paths
  indexed."
- "Put anything slow or unreliable, like an LLM call, behind a queue, with a fallback."
- "Elasticity is scaling *in* as well as out, and that's where the cost savings come from."
- "Measure first: p95 latency, error rate and saturation drive the next change."
