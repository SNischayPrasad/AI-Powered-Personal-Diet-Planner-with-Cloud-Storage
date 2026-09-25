# 01 · Project explanation

## A. Simple explanation

Imagine a nutrition notebook that lives on the internet instead of in your bag.

1. You create an account, like on any website.
2. You tell the app a few things about yourself: age, height, weight, how active you are,
   whether you eat vegetarian, vegan or everything, what you are aiming for, and any foods
   you must avoid.
3. The app works out roughly how much energy you need in a day and builds a sample day of
   meals (breakfast, lunch, snack and dinner) that fits your choices. It also reminds you to
   drink water.
4. The plan is saved **in the cloud**, not on your phone. Log in from a laptop, a college
   computer or a new phone and your plans are still there.
5. You can upload photos of your meals and save a copy of any plan as a file. Those files are
   also kept in the cloud.

It is a demo for learning: the plans are general examples, not advice from a doctor or
dietitian.

## B. Technical explanation

The project is a **three-tier cloud application**:

- a **React single-page app** (presentation tier), and
- a **stateless FastAPI REST API** (application tier), backed by
- two different managed storage services (data tier):
  - a **relational database** (SQLite locally, PostgreSQL in the cloud) for structured
    records, and
  - an **S3-compatible object store** for binary files.

Authentication uses bcrypt password hashes and signed JWT access tokens, with server-side
revocation on logout. The **AI layer** computes energy targets with the Mifflin-St Jeor
equation. It then either:

- asks an LLM for dishes under a strict JSON schema and validates the answer, or
- uses a deterministic rule-based recommender over a curated food dataset.

Any LLM failure or unsafe answer falls back to the rules. All configuration (database URL,
storage provider, AI provider, secrets) comes from environment variables, so the same
container image runs on a laptop, in CI, on Render, on Vercel or on AWS.

## Workflow

```text
User
 ↓  opens the site in a browser
Web application (React)
 ↓  POST /api/register or /api/login
Authentication (bcrypt check → signed JWT)
 ↓  PUT /api/profile
User profile input (validated: ranges, enumerated options)
 ↓  POST /api/generate-plan   (Authorization: Bearer <JWT>)
Cloud backend / API (FastAPI: verify token → load this user's profile)
 ↓
AI diet planner (targets → LLM or rules → validation → fallback)
 ↓
Personalised plan (4 meals, nutrition summary, hydration, tips, disclaimer)
 ↓  INSERT diet_plans
Cloud database (PostgreSQL / SQLite)
 ↓  optional: save export, upload meal photos
Cloud storage (S3-compatible bucket, private)
 ↓  GET /api/plans, /api/files
User dashboard (latest plan, history, files, cloud status)
```

## Questions the brief asks

**What problem does it solve?** Generic diet charts ignore the person, and notes on one
device get lost. The app gives a quick, personalised, explainable starting point that you
can reach from anywhere, while keeping each person's data private.

**Why is cloud computing useful here?**
- Users on different devices need one shared, always-on source of truth.
- The load is uneven (lunchtime spikes, exam weeks), so elastic, pay-per-use hosting fits
  better than a fixed server.
- Managed databases and storage give backups, encryption and durability that a student
  could not run alone.
- An AI API is itself a cloud service consumed over HTTPS.

**Why store user data centrally?**
- A single copy that every device reads avoids conflicting versions.
- Server-side authorization is enforced in one place.
- Backups and encryption at rest are handled by the provider.
- The data survives a lost or broken phone.

**How can AI personalise meal plans?** The app turns the profile into numbers and
constraints: calorie target, macro targets, per-meal budgets, allowed diet and excluded
allergens. It then chooses dishes that satisfy them. The rule-based engine does this with
filters and scoring. An LLM can propose more varied dishes, but only inside the same
constraints, and its answer is checked before use. See [07 · AI engine](07-ai-engine.md).

**How do users access saved plans from different devices?** Plans live in the cloud
database, keyed by user ID. Logging in on any device returns a token, and `GET /api/plans`
returns that user's plans.

**How do cloud databases and cloud storage differ?**

| | Cloud database | Cloud object storage |
|---|---|---|
| Holds | Structured records: users, profiles, plans, file metadata | Files: images, PDFs, exported plans |
| Access | SQL queries, filters, joins, transactions | Put, get or delete a whole object by key |
| Strength | Consistency, querying, relationships | Cheap, durable, virtually unlimited size |
| In this project | `users`, `diet_plans`, `user_files`, `revoked_tokens` | `users/<id>/meal-images/<uuid>.png`, `…/plan-exports/…` |

**How do the parts communicate?** The browser talks only to the API, over HTTPS with JSON
and a Bearer token. The API talks to the database through SQLAlchemy (a connection pool)
and to storage through the `StorageService` interface (boto3 for S3). It reaches the AI
provider over HTTPS with a server-side API key. The browser never sees database
credentials, storage keys or AI keys.
