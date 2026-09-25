# Security policy

This is an educational project that uses **synthetic data only**. Please don't enter real
personal or health information into any deployment of it.

## Reporting a vulnerability

Please report security issues privately through GitHub's
[private vulnerability reporting](https://github.com/SNischayPrasad/AI-Powered-Personal-Diet-Planner-with-Cloud-Storage/security/advisories/new),
not in a public issue. If that option is not shown, open an issue asking for a private
contact, without any vulnerability details. Include steps to reproduce and the impact. You should get a response
within a week.

## Supported versions

Only the latest commit on `main` is maintained.

## Security design at a glance

- Passwords hashed with bcrypt; signed, expiring JWTs with server-side revocation on logout.
- Every data access is scoped to the authenticated user; other users' resources return 404.
- Input validated with Pydantic; uploads checked by content (magic bytes), size and quota.
- Rate limiting on authentication and plan generation.
- Secrets only in environment variables (`.env` is gitignored and excluded from Docker
  images); production refuses a weak JWT secret.
- Private object storage; downloads only through the API after an ownership check.
- Security headers (CSP, HSTS in production, X-Frame-Options, nosniff); CORS allow-list.
- Non-root container image; CI runs `ruff` security rules on every push.
- AI prompts contain no personal data, and AI output is validated before use.

Details: [docs/17-security.md](docs/17-security.md).
