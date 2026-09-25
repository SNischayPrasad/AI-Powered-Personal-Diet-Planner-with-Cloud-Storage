# 15 · Cloud deployment

The same code runs on a laptop and in the cloud. The difference is configuration: environment
variables choose the database, object storage and AI provider (see
[`backend/config.py`](../backend/config.py) and [`.env.example`](../.env.example)).

| Concern | Local simulation | Approach A: free tier | Approach B: AWS |
|---|---|---|---|
| Frontend | Vite dev server (`:5173`) | Served by the API container (Render), or Vercel's CDN | Served by the API container, optionally behind CloudFront |
| Backend | `uvicorn` on your machine | Render web service (Docker) or a Vercel Python function | Amazon ECS on Fargate behind an Application Load Balancer |
| Database | SQLite file, or PostgreSQL in Docker | Neon or Supabase PostgreSQL | Amazon RDS for PostgreSQL |
| Object storage | Folder `data/object_storage`, or RustFS (S3 API) in Docker | Supabase Storage or Cloudflare R2 (S3 API) | Amazon S3, private bucket |
| Secrets | `.env` file (gitignored) | Hosting dashboard environment variables | AWS Secrets Manager plus an IAM task role |
| Logs and metrics | Console, `/api/metrics` | Render / Vercel log viewer | CloudWatch Logs and alarms |
| Cost | Free | Free (with limits, see below) | Free tier for 12 months on new accounts, then pay as you go |

> Status: the Docker image is built, run and smoke-tested on every push by the `docker` CI job,
> both alone and with PostgreSQL + an S3-compatible server (RustFS). The Render, Vercel and AWS steps below follow each
> provider's documented setup, but they were not run against a live account for this project.
> Run the smoke test after your first deploy.

## What gets deployed

```text
            ┌──────────────── one container image (Dockerfile) ────────────────┐
browser ──▶ │  FastAPI                                                          │
            │   /api/*      REST API (auth, profile, plans, files, health)      │
            │   /assets/*   fingerprinted JS/CSS/fonts (cached for a year)      │
            │   /*          React app (index.html, never cached)                │
            └──────┬──────────────────────────┬──────────────────────┬──────────┘
                   │ DATABASE_URL             │ S3 API               │ HTTPS (optional)
            PostgreSQL (managed)       Object storage bucket     Claude / OpenAI-compatible
```

- **[`Dockerfile`](../Dockerfile)** is a multi-stage build. Node 22 builds the React app, then
  a slim Python 3.13 image runs it as a non-root user. It has a `HEALTHCHECK` and binds to
  the `PORT` the platform provides.
- **[`backend/utils/spa.py`](../backend/utils/spa.py)** serves the React build when
  `FRONTEND_DIST_DIR` is set. Unknown `/api/...` paths still return JSON 404s, and client-side
  routes such as `/dashboard` fall back to `index.html`.
- **One origin** means no CORS setup and the strict Content-Security-Policy
  (`default-src 'self'`) works unchanged.

## Environment variables for the cloud

| Variable | Example | Notes |
|---|---|---|
| `ENVIRONMENT` | `production` | Refuses to start without a strong `JWT_SECRET_KEY` |
| `JWT_SECRET_KEY` | 48+ random characters | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DATABASE_URL` | `postgresql://…` | `postgres://` URLs are accepted too |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | `3`, `2` | Keep small on free database plans |
| `STORAGE_PROVIDER` | `s3` | `local` keeps files on the container disk, which is lost on redeploy |
| `STORAGE_BUCKET` | `diet-planner-files` | The bucket must exist and be **private** |
| `S3_ENDPOINT_URL` | see provider | Empty for AWS S3 |
| `S3_REGION` | `ap-south-1` | |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | provider keys | Leave empty on AWS so the IAM role is used |
| `S3_FORCE_PATH_STYLE` | `true` | For Supabase Storage, R2 and the Docker S3 server |
| `TRUST_PROXY_HEADERS` | `true` | Rate limiting then sees the real client IP behind the platform proxy |
| `LOG_FORMAT` | `json` | One JSON object per line for cloud log search |
| `CORS_ORIGINS` | `https://your-frontend.vercel.app` | Only needed when the frontend is on another domain |
| `AI_PROVIDER` | `rule_based` | Or `anthropic` / `openai_compatible` plus the matching key |
| `FRONTEND_DIST_DIR` | `/app/frontend/dist` | Already set in the Docker image |

Never commit any of these values. Each platform stores them encrypted and injects them at run
time.

---

## Approach A: free tier (Render + Neon/Supabase)

### A.1 Create the cloud database

**Neon** (neon.tech → New project):
1. Pick a region close to your Render region (e.g. AWS Singapore).
2. Copy the **pooled** connection string. Its host contains `-pooler`, and it ends with
   `?sslmode=require`.

**Or Supabase** (supabase.com → New project):
1. Project Settings → Database → Connection string → **Transaction pooler** (port 6543).
2. Replace `[YOUR-PASSWORD]` with the database password you chose.

The tables are created automatically on first start. The app also retries after an outage:
readiness reports `degraded` until the database is reachable.

### A.2 Create the object storage bucket

**Supabase Storage** (the same project works):
1. Storage → New bucket → name `diet-planner-files`, **Public bucket off**.
2. Storage → Settings → S3 Connection → enable it, then create an access key.
3. Note the endpoint `https://<project-ref>.supabase.co/storage/v1/s3` and the region shown.

**Or Cloudflare R2**: create bucket `diet-planner-files`, then an R2 API token with
Object Read & Write on that bucket only. The endpoint is
`https://<account-id>.r2.cloudflarestorage.com`, and the region is `auto`.

The app never makes objects public. Downloads always go through the API, which checks that the
file belongs to the logged-in user.

### A.3 Deploy the app on Render (recommended)

1. Push the repository to GitHub (already done).
2. Render dashboard → **New → Blueprint** → select the repository. Render reads
   [`render.yaml`](../render.yaml) and proposes one free Docker web service.
3. Fill in the values marked `sync: false`: `DATABASE_URL`, `S3_ENDPOINT_URL`, `S3_REGION`,
   `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` (and `ANTHROPIC_API_KEY` only if you use Claude).
   `JWT_SECRET_KEY` is generated by Render.
4. Click **Apply**. The first build takes a few minutes. Render waits for
   `/api/health/ready` to return 200 before it sends traffic to the new version.
5. Open `https://<service>.onrender.com` and run the smoke test from your laptop:

   ```bash
   python scripts/smoke_test.py --base-url https://<service>.onrender.com
   ```

**Continuous deployment:** every push to `main` redeploys (`autoDeploy: true`). GitHub
Actions runs the tests on the same push. For stricter gating, set Render's auto-deploy to
"After CI checks pass".

**Free tier limits:** 512 MB RAM, the service sleeps after about 15 minutes idle (the first
request then takes 30–60 seconds), and there is no persistent disk. That is why the database
and files live in Neon/Supabase.

### A.4 Alternative: frontend on Vercel, API on Render

Useful to show a CDN-hosted frontend talking to a separate API:

1. Deploy the API on Render as above.
2. Vercel → Add New Project → import the repository → **Root Directory `frontend`**. Vercel
   detects Vite; [`frontend/vercel.json`](../frontend/vercel.json) adds the SPA fallback and
   long-lived caching for `/assets/*`.
3. Environment variable on Vercel: `VITE_API_BASE_URL=https://<service>.onrender.com`.
4. On Render, set `CORS_ORIGINS=https://<project>.vercel.app` so the browser may call the API.

### A.5 Alternative: everything on Vercel

[`vercel.json`](../vercel.json) builds the React app into static files and runs the API as a
Python function from [`api/index.py`](../api/index.py). Requests to `/api/*` go to the
function, and every other path gets the React app.

1. Vercel → Add New Project → import the repository, **Root Directory = repository root**.
2. Environment variables: everything from the table above. `DATABASE_URL` and
   `STORAGE_PROVIDER=s3` are **required**, because the function's filesystem is read-only.
   Use the **pooled** database URL with `DB_POOL_SIZE=1` and `DB_MAX_OVERFLOW=0`, since each
   function instance opens its own connections.
3. Deploy, then run the smoke test against `https://<project>.vercel.app`.

Trade-offs: cold starts on the first request, and the in-memory rate limiter counts per
function instance (see [scalability](18-scalability.md)). Render (A.3) is the simpler choice
for a demo.

---

## Approach B: AWS (production-style)

```text
Route 53 ─▶ CloudFront (optional) ─▶ ALB (HTTPS, ACM certificate)
                                       │
                          ECS service on Fargate (2+ tasks, 2 AZs)
                          image from ECR · IAM task role · logs → CloudWatch
                             │                         │
                 RDS PostgreSQL (private subnets)   S3 bucket (private, encrypted)
                 secrets in Secrets Manager
```

| Need | AWS service | Why |
|---|---|---|
| Container registry | Amazon ECR | Stores the Docker image built from the `Dockerfile` |
| Compute | Amazon ECS on Fargate | Runs containers without managing servers; scales on CPU |
| Load balancing and HTTPS | Application Load Balancer + ACM | TLS termination, health checks on `/api/health/ready` |
| Database | Amazon RDS for PostgreSQL | Managed backups, patching, Multi-AZ failover |
| Object storage | Amazon S3 | Durable, private meal images and plan exports |
| Secrets | AWS Secrets Manager | `DATABASE_URL`, `JWT_SECRET_KEY`, AI keys, injected into the task |
| Permissions | IAM task role | S3 access without any access keys in configuration |
| Logs and monitoring | CloudWatch Logs, metrics and alarms | JSON logs are searchable with Logs Insights |
| CDN (optional) | CloudFront | Caches `/assets/*` at the edge |

Simpler options: AWS App Runner or Elastic Beanstalk (Docker platform) can also run this image
with fewer moving parts. Check that the service is available to your account and region first.

### B.1 Build and push the image

```bash
aws ecr create-repository --repository-name diet-planner
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.ap-south-1.amazonaws.com
docker build -t diet-planner .
docker tag diet-planner:latest <account-id>.dkr.ecr.ap-south-1.amazonaws.com/diet-planner:latest
docker push <account-id>.dkr.ecr.ap-south-1.amazonaws.com/diet-planner:latest
```

### B.2 Create the database and bucket

1. **RDS**: PostgreSQL, `db.t4g.micro` (free-tier eligible), in **private subnets**, with
   public access off. Its security group allows port 5432 only from the ECS tasks' security
   group. Encryption at rest on, automated backups on.
2. **S3**: bucket `diet-planner-files-<account-id>` with Block Public Access (all four) on and
   default encryption (SSE-S3). Versioning is optional and protects against accidental
   deletes.
3. **Secrets Manager**: store `DATABASE_URL`
   (`postgresql://<user>:<password>@<rds-endpoint>:5432/dietplanner?sslmode=require`) and
   `JWT_SECRET_KEY`.

### B.3 Least-privilege IAM task role

The app only needs its own bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::diet-planner-files-<account-id>/users/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::diet-planner-files-<account-id>"
    }
  ]
}
```

Leave `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` unset. boto3 then picks up the role's
temporary credentials automatically.

### B.4 ECS service

- **Task definition**: 0.5 vCPU / 1 GB, container port 8000, the image from ECR. Plain
  environment: `ENVIRONMENT=production`, `LOG_FORMAT=json`, `TRUST_PROXY_HEADERS=true`,
  `STORAGE_PROVIDER=s3`, `STORAGE_BUCKET`, `S3_REGION`. Secrets from Secrets Manager:
  `DATABASE_URL`, `JWT_SECRET_KEY`. Log driver `awslogs`.
- **Service**: 2 tasks across 2 Availability Zones behind the ALB. Target group health check
  on `/api/health/ready`. Rolling deployments with circuit breaker and rollback on.
- **Auto scaling**: target tracking at 60 % average CPU, minimum 2 and maximum 6 tasks.
- **Alarms**: ALB 5xx count, target response time p95, RDS CPU and free storage.

### B.5 Continuous deployment

Extend the CI workflow with a deploy job that runs only on `main` after all tests pass. Use
GitHub's OIDC provider to assume an AWS role, so no long-lived AWS keys are stored in GitHub.
Then build, push to ECR, and run `aws ecs update-service --force-new-deployment`.

### Azure and Google Cloud equivalents

| Component | AWS | Azure | Google Cloud |
|---|---|---|---|
| Containers | ECS Fargate / App Runner | Azure Container Apps | Cloud Run |
| Registry | ECR | Azure Container Registry | Artifact Registry |
| PostgreSQL | RDS | Azure Database for PostgreSQL (Flexible Server) | Cloud SQL for PostgreSQL |
| Object storage | S3 | Blob Storage | Cloud Storage |
| Secrets | Secrets Manager | Key Vault | Secret Manager |
| Logs | CloudWatch | Azure Monitor / Log Analytics | Cloud Logging |
| Identity for storage | IAM task role | Managed identity | Service account |

The storage layer speaks the S3 API. Google Cloud Storage offers an S3-compatible
"interoperability" endpoint (`https://storage.googleapis.com` with HMAC keys), so it works
through configuration alone. Azure Blob Storage has no S3 API. There you would add an
`AzureBlobStorageService` next to `S3StorageService` in
[`cloud/storage_service.py`](../cloud/storage_service.py). Nothing else changes, because the
rest of the app only knows the `StorageService` interface.

---

## Run the production image locally

With Docker Desktop, this starts the exact image that ships to the cloud, wired to PostgreSQL
and RustFS (S3-compatible storage):

```bash
docker compose --profile app up --build
```

Then open http://localhost:8000. `.env` needs `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`,
`RUSTFS_ACCESS_KEY` and `RUSTFS_SECRET_KEY`. Use letters and digits in the Postgres password,
because it is embedded in a URL.

## After every deployment

1. `GET /api/health`: the process is up.
2. `GET /api/health/ready`: database and storage are reachable (200, or 503 with details).
3. `GET /api/system/status`: confirms `database_provider=postgresql` and
   `storage_provider=s3`.
4. `python scripts/smoke_test.py --base-url <url>`: 28 checks across the whole user journey.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Deploy fails: "JWT_SECRET_KEY must be … at least 32 characters" | Missing or short secret in production | Set a long random value |
| `/api/health/ready` returns 503 with `database: false` | Wrong URL, password or SSL mode; IP allow-list | Check `DATABASE_URL`; add `?sslmode=require`; allow the host |
| Uploads return 503 `storage_unavailable` | Bucket missing, wrong endpoint/region, or key without write access | Create the bucket; check `S3_*` values; for Supabase/R2 set `S3_FORCE_PATH_STYLE=true` |
| "too many connections" on the free database | Too many instances × pool size | Use the pooled URL; lower `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` |
| All users share one rate limit | Proxy IP used instead of the client IP | `TRUST_PROXY_HEADERS=true` |
| Browser shows CORS errors | Frontend on another domain | Add its exact origin to `CORS_ORIGINS` |
| First request after a while is slow | Free service woke up from sleep | Expected on free tiers |
