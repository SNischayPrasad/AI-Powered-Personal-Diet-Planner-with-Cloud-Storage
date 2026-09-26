# 12 · Project folder structure

The layout follows the brief's structure. The repository name differs
(`AI-Powered-Personal-Diet-Planner-with-Cloud-Storage`), and a few production files are
added: Docker, CI and deployment configs.

```text
AI-Powered-Personal-Diet-Planner-with-Cloud-Storage/
│
├── frontend/                     React 19 + Vite single-page app
│   ├── index.html                HTML shell; Vite injects the bundles
│   ├── package.json · package-lock.json   dependencies (locked) and scripts: dev, build, test
│   ├── vite.config.js            dev server on 5173, /api proxy → 8000, Vitest config
│   ├── vercel.json               SPA fallback + asset caching when Vercel hosts only the frontend
│   ├── .env.example              VITE_API_BASE_URL (only when the API is on another domain)
│   ├── public/favicon.svg        thali icon
│   └── src/
│       ├── main.jsx · App.jsx    entry point, routes, providers
│       ├── pages/                Landing, Register, Login, Profile, GeneratePlan, PlanResult,
│       │                         SavedPlans, CloudFiles, Dashboard, NotFound
│       ├── components/           reusable UI (Thali, MealCard, MacroMeters, UploadDropzone,
│       │                         RouteGuards, CloudStatusPanel, Navbar, …)
│       ├── services/             apiClient.js (the only fetch wrapper) + auth/profile/plan/file/system services
│       ├── context/              AuthContext.jsx: session state, login/register/logout
│       ├── hooks/                useDocumentTitle, useFilePreview
│       ├── utils/                formatting, option labels, thali geometry, downloads (+ *.test.js)
│       └── styles/               tokens.css (design tokens), global.css
│
├── backend/                      FastAPI REST API
│   ├── app.py                    application factory create_app(): wires everything; `app` for uvicorn
│   ├── config.py                 typed settings from environment variables (.env locally)
│   ├── routes/                   HTTP layer, one router per area
│   │   ├── auth_routes.py        /register /login /logout
│   │   ├── profile_routes.py     /profile
│   │   ├── plan_routes.py        /generate-plan /plans … /export /save-to-cloud
│   │   ├── file_routes.py        /upload /files … /download
│   │   └── system_routes.py      /health /health/ready /system/status /metrics
│   ├── services/                 business logic (no HTTP details)
│   │   ├── auth_service.py       register, authenticate, revoke tokens
│   │   ├── profile_service.py    read/update profile, completeness
│   │   ├── plan_service.py       build the plan request, call the planner, save/list/delete (user-scoped)
│   │   ├── file_service.py       validate, store, list, download, delete files; quota; compensating delete
│   │   └── export_service.py     plan → JSON / text report
│   ├── models/
│   │   ├── db_models.py          SQLAlchemy tables: users, diet_plans, user_files, revoked_tokens
│   │   └── schemas.py            Pydantic request/response models (validation + OpenAPI docs)
│   └── utils/
│       ├── security.py           bcrypt hashing, JWT create/verify
│       ├── dependencies.py       CurrentUser, DbSession, Storage … (dependency injection)
│       ├── errors.py             AppError hierarchy → consistent JSON errors; DB/storage outage → 503
│       ├── middleware.py         request IDs, access logs, metrics, security headers (CSP, HSTS…)
│       ├── rate_limiter.py       sliding-window limiter (auth, plan generation)
│       ├── file_validation.py    magic-byte type detection, filename sanitising
│       ├── metrics.py            Prometheus-text counters
│       ├── logging_config.py     text or JSON logs with request IDs
│       └── spa.py                serves the React build from the API (single-container deploys)
│
├── ai_engine/                    diet recommendation "AI"
│   ├── options.py                allowed values (diets, goals, allergens…), shared by API, DB and prompts
│   ├── nutrition.py              BMR → TDEE → target → macros → meal budgets → water
│   ├── diet_engine.py            Version A: rule-based engine; plan assembly; disclaimer
│   ├── food_data.json            65 dishes: slots, diet tags, allergens, cuisine, nutrition, portions
│   ├── prompts.py                Version B: system prompt, structured user prompt, JSON schema
│   ├── llm_providers.py          Claude (Anthropic SDK) and OpenAI-compatible (HTTP) providers
│   ├── validation.py             guardrails for LLM answers
│   └── planner.py                AI first → validate → rule-based fallback, with a reason
│
├── cloud/                        cloud adapters: swap providers by configuration
│   ├── database_service.py       SQLAlchemy engine: SQLite / PostgreSQL, pooling, health check
│   └── storage_service.py        StorageService: LocalStorageService | S3StorageService
│
├── api/index.py                  Vercel serverless entry point (imports backend.app:app)
│
├── cloudflare/                   Cloudflare Worker (the public front door)
│   ├── wrangler.jsonc            Worker config: static assets from ../frontend/dist, SPA fallback, API_ORIGIN
│   ├── src/index.js              serves pages with security headers; proxies /api/* to the FastAPI service
│   ├── test/worker.test.js       unit tests (node --test)
│   └── package.json · package-lock.json   wrangler; scripts: dev, deploy, test
│
├── tests/                        297 pytest tests
│   ├── conftest.py · helpers.py  isolated app per test (temporary SQLite + bucket, or TEST_DATABASE_URL)
│   ├── ai_fixtures.py            canned LLM answers (valid, unsafe, malformed)
│   ├── test_auth.py              TC-01…05, TC-19
│   ├── test_profile.py           TC-05 (profile), TC-06
│   ├── test_plans.py             TC-07…10, TC-13, TC-14
│   ├── test_ai_fallback.py       TC-11, TC-12 and guardrails
│   ├── test_files.py             TC-15…17, TC-20 (storage outage)
│   ├── test_isolation.py         TC-18
│   ├── test_database.py          TC-20 (database outage, recovery), PostgreSQL URL handling
│   ├── test_health.py            probes, metrics, security headers
│   ├── test_diet_engine.py       TC-08…10 at engine level, nutrition maths
│   ├── test_storage_service.py · test_llm_providers.py · test_security.py
│   └── test_spa.py · test_deployment.py · test_seed_script.py
│
├── scripts/
│   ├── smoke_test.py             28-check end-to-end test against any running deployment
│   ├── seed_demo_data.py         loads the synthetic demo users through the API
│   └── capture_screenshots.py    regenerates screenshots/ with Playwright
│
├── sample_data/                  synthetic demo users, two meal illustrations, sample plan exports
├── screenshots/                  images used in the README
├── docs/                         this documentation (20 chapters)
│
├── .github/workflows/ci.yml      CI: lint, tests (SQLite, PostgreSQL), frontend, smoke, Docker full stack
├── Dockerfile · .dockerignore    production image (frontend build + API, non-root)
├── docker-compose.yml            local cloud: PostgreSQL + RustFS (S3); `--profile app` runs the image
├── render.yaml                   Render Blueprint (free tier)
├── vercel.json · .vercelignore   Vercel full-stack deployment
├── requirements.txt              runtime Python dependencies
├── requirements-dev.txt          + pytest, coverage, moto, ruff
├── pyproject.toml                pytest, coverage and ruff configuration
├── .env.example                  every environment variable, documented (copy to .env)
├── .gitignore · .gitattributes · .editorconfig
├── LICENSE                       MIT
├── SECURITY.md                   security policy and design summary
└── README.md
```

## Generated at run time (gitignored)

| Path | Contents |
|---|---|
| `data/diet_planner.db` | Local SQLite database |
| `data/object_storage/<bucket>/users/…` | Local simulated bucket |
| `frontend/node_modules/`, `frontend/dist/` | npm packages, production build |
| `.venv/` | Python virtual environment |
| `.env` | Your local secrets and settings |
