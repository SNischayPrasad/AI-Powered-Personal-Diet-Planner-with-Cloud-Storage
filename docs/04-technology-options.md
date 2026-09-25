# 04 · Technology stack options

Three ways to build the same product, from simplest to most production-like.

## Option A: Beginner

| Layer | Choice |
|---|---|
| Frontend | HTML, CSS, JavaScript (server-rendered templates) |
| Backend | Python Flask |
| Database | SQLite |
| AI | Rule-based engine |
| Storage | Local folder that simulates a bucket |
| Deployment | A free web host (e.g. Render free web service, PythonAnywhere) |

- **Architecture:** one process renders pages and stores data on its own disk.
- **Difficulty:** low. One language, no build step.
- **Cost:** free.
- **Cloud concepts shown:** hosting, client-server, basic authentication.
- **Expected output:** a working app on one URL, but data is lost when the host
  redeploys (the disk is ephemeral), and it cannot scale beyond one instance.

## Option B: Recommended (student-friendly, cloud-native) ✅ *implemented*

| Layer | Choice in the brief | What this project uses |
|---|---|---|
| Frontend | React | React 19 + Vite |
| Backend | FastAPI or Flask | **FastAPI** (typed, automatic OpenAPI docs, fast) |
| Authentication | Firebase Auth or equivalent | **Own JWT auth** (bcrypt + signed tokens + revocation), to show how it works inside. It can be swapped for Supabase Auth / Firebase / Cognito |
| Database | Firestore / Supabase / cloud DB | **PostgreSQL** on Supabase or Neon (SQLite locally) |
| Cloud storage | Firebase Storage / Supabase Storage | **Any S3-compatible store**: Supabase Storage, Cloudflare R2, AWS S3; RustFS in Docker; a folder locally |
| AI | AI API or local rule-based fallback | Rule-based engine + optional **Claude** or **OpenAI-compatible** API with validation and fallback |
| Deployment | Free-tier cloud hosting | Render (Docker) or Vercel, plus Neon / Supabase |

- **Architecture:** SPA → stateless REST API → managed PostgreSQL + object storage (+ AI
  API).
- **Difficulty:** medium. Two languages and several services, but each is managed.
- **Cost:** ₹0 on free tiers (limits: sleeping services, small databases, storage caps). An
  LLM is optional; Gemini and Groq have free tiers, and Ollama runs locally.
- **Cloud concepts shown:** SaaS / PaaS, managed database, object storage, stateless
  scaling, secrets in the environment, health checks, CI/CD, serverless (Vercel).
- **Expected output:** a public URL, persistent data, files in a real bucket, automated
  tests on every push.

**Why custom JWT instead of Firebase Auth?** Examiners and interviewers ask *how*
authentication works: hashing, token signing, expiry and revocation. Building it (with
well-tested libraries, never custom crypto) shows that, and keeps the app free of vendor
lock-in. Firestore was not used because plans, files and users are relational and benefit
from SQL, foreign keys and transactions.

## Option C: Advanced (enterprise cloud)

| Layer | Choice |
|---|---|
| Frontend | React / Next.js on CloudFront + S3, or Amplify |
| Backend | FastAPI on ECS Fargate or AWS Lambda behind API Gateway |
| Auth | Amazon Cognito (OIDC), or Azure AD B2C / Google Identity Platform |
| Database | RDS / Aurora PostgreSQL (Multi-AZ, read replicas) |
| Storage | S3 with presigned URLs; CloudFront for images |
| AI | Amazon Bedrock or a direct LLM API, called from an SQS-driven worker |
| Monitoring | CloudWatch, X-Ray / OpenTelemetry, alarms |
| IaC and CD | Terraform / CDK; GitHub Actions with OIDC → AWS |

- **Architecture:** multi-AZ, auto-scaled, event-driven for slow AI calls.
- **Difficulty:** high. Networking, IAM and infrastructure as code.
- **Cost:** partly free-tier for 12 months, then pay-as-you-go. A NAT gateway and load
  balancer cost money even when idle.
- **Cloud concepts shown:** everything in B, plus VPC design, IAM least privilege,
  queues, CDN, managed identity, observability, infrastructure as code.
- **Expected output:** a production-grade, highly available deployment.

This repository already runs on Option C's compute (the same Docker image). Approach B in
[15 · Deployment](15-cloud-deployment.md) documents the AWS architecture.

## Comparison and recommendation

| | A: Beginner | **B: Recommended** | C: Advanced |
|---|---|---|---|
| Time to build | Days | 2–4 weeks | Months |
| Monthly cost | ₹0 | ₹0 | ₹0 → ₹₹ after free tier |
| Data survives redeploys | ✗ | ✓ | ✓ |
| Scales horizontally | ✗ | ✓ | ✓✓ |
| Cloud concepts covered | Few | Most | All |
| Good for interviews | Basic | **Strong** | Strong, but hard to finish |

**Recommendation: Option B.** It demonstrates nearly every concept in the course for free,
runs fully offline for demos, and is one configuration change away from Option C's AWS
services, which [15 · Deployment](15-cloud-deployment.md) shows.
