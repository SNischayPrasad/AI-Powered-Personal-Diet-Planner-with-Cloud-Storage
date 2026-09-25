# 19 · GitHub upload strategy

## Repository settings

| Setting | Value |
|---|---|
| Name | `AI-Powered-Personal-Diet-Planner-with-Cloud-Storage` (the brief suggested `AI-Powered-Personal-Diet-Planner-Cloud`; the longer name matches the project title) |
| Description | *Cloud-based AI-powered personal diet planning application with authentication, personalized recommendation generation, cloud database integration, object storage, and scalable deployment architecture.* |
| Topics | `cloud-computing` `artificial-intelligence` `python` `fastapi` `react` `cloud-storage` `database` `rest-api` `full-stack` `cloud-application` `postgresql` `object-storage` `aws-s3` `jwt-authentication` `llm` `sqlalchemy` `vite` `github-actions` `diet-planner` |
| Visibility | Public, so it serves as proof of work |
| License | MIT |

`flask` and `firebase` from the brief's topic list are left out on purpose: the project
uses FastAPI and PostgreSQL / S3-compatible storage, and topics should describe what is
actually in the repository.

Set them from the command line with the GitHub CLI:

```bash
gh repo edit --description "Cloud-based AI-powered personal diet planning application with authentication, personalized recommendation generation, cloud database integration, object storage, and scalable deployment architecture." --add-topic cloud-computing,artificial-intelligence,python,fastapi,react,cloud-storage,database,rest-api,full-stack,cloud-application
```

## First push

```bash
git init
git add .
git commit -m "Initialize cloud diet planner project"
git branch -M main
git remote add origin https://github.com/SNischayPrasad/AI-Powered-Personal-Diet-Planner-with-Cloud-Storage.git
git push -u origin main
```

Before the first `git add .`, check that `git status` doesn't list `.env`, `data/`,
`.venv/` or `node_modules/`. [`.gitignore`](../.gitignore) excludes them.

## Commit history (as built)

Each commit is a working, tested step, so the history reads like the project's story:

| # | Commit message | What it added |
|---|---|---|
| 1 | Initialize cloud diet planner project | Package layout, dependencies, tool config, `.gitignore`, licence |
| 2 | Create cloud application architecture | App factory, settings, `.env.example`, database service, health checks, middleware |
| 3 | Add user authentication | Register, login, logout, bcrypt, JWT, revocation, rate limiting |
| 4 | Implement user profile management | Profile API and validation |
| 5 | Add AI diet recommendation engine | Nutrition maths, food dataset, rule-based engine |
| 6 | Implement diet plan REST API | Generate, list, get, delete, export |
| 7 | Integrate cloud database | PostgreSQL support, connection pooling, resilient start-up, PostgreSQL in Docker Compose |
| 8 | Add cloud object storage | Uploads, S3 adapter, quotas, save-to-cloud |
| 9 | Build user dashboard | The React frontend |
| 10 | Add AI fallback mechanism | LLM providers, prompts, validation, fallback |
| 11 | Add application tests | TC-01 … TC-20 table, isolation tests, smoke test, CI pipeline (SQLite + PostgreSQL) |
| 12 | Deploy application to cloud | Dockerfile, Render, Vercel, Docker Compose, CI full-stack job, deployment guide |
| 13 | Complete README and documentation | README, 20 docs chapters, screenshots, sample data, seed script |

## Working practices

- **Small, focused commits** with imperative messages ("Add…", "Fix…"). The subject line
  stays under about 60 characters, and the body explains *why*.
- **Branches and pull requests** for new work, even when working alone:

  ```bash
  git switch -c feature/weekly-plans
  git push -u origin feature/weekly-plans
  gh pr create --fill
  ```

  CI runs on the PR, and you merge only when it is green.
- **Protect `main`** (Settings → Branches): require the CI checks to pass before merging.
- **Never commit secrets.** If one leaks, rotate it first, then clean up.
- **Releases**: tag milestones so reviewers can see versions:

  ```bash
  git tag -a v1.0.0 -m "Course submission"
  git push origin v1.0.0
  gh release create v1.0.0 --generate-notes
  ```

- **Issues** for the ideas in *Future improvements*. They show you plan work like a team.

## Making the repository recruiter-ready

- [x] README with a screenshot at the top, badges, and a clear problem, solution and results
- [x] CI badge that is green, with tests that really run (SQLite, PostgreSQL, Docker full
      stack)
- [x] Documentation in `docs/` a reviewer can skim
- [x] Synthetic data only, and a disclaimer
- [x] A licence, and a security policy ([`SECURITY.md`](../SECURITY.md))
- [ ] Pin the repository on your GitHub profile
- [ ] Add the live demo URL (Render) to the repository's "About" box once deployed
- [ ] Share it on LinkedIn with 2–3 screenshots and what you learned
