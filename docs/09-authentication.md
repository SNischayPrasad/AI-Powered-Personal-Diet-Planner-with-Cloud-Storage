# 09 · Authentication and authorization

## Concepts

| Term | Question it answers | In this project |
|---|---|---|
| **Authentication** | *Who are you?* | Email + password at login → a signed token; the token on every later request |
| **Authorization** | *What may you do?* | Every data query is scoped to the token's user; other users' IDs return 404 |
| **Session (stateful)** | Server remembers the login in memory or a store | Not used, because it would tie users to one server |
| **JWT (stateless)** | The client carries a signed statement of identity | Used: any instance can verify it with the shared secret |

## Flow

```text
Register / Login                               Every protected request
────────────────                               ───────────────────────
POST /api/login {email, password}              GET /api/plans
   │ rate limit (10/min per client)              Authorization: Bearer eyJhbGciOi…
   │ find user by lower-cased email                 │ 1. decode + verify HS256 signature
   │ bcrypt.checkpw(password, hash)                 │ 2. check exp (expiry) and type="access"
   │   (same error for unknown email                │ 3. check jti not in revoked_tokens
   │    and wrong password)                         │ 4. load the user by sub
   ▼                                                ▼
200 {access_token, expires_in, user}           handler runs with CurrentUser
                                               (else 401 + WWW-Authenticate: Bearer)
Logout: POST /api/logout → INSERT revoked_tokens(jti, expires_at) → token dead immediately
```

## Password security

- **bcrypt** with a work factor of 12 (`BCRYPT_ROUNDS`, in
  [`security.py`](../backend/utils/security.py)). It is deliberately slow, salted per
  password (the same password gives different hashes), and compared in constant time.
- **Policy**: at least 8 characters with at least one letter and one number. At most 72
  bytes, because bcrypt ignores anything longer and we refuse to truncate silently.
- **Never stored, logged or returned.** API responses use the `UserProfile` schema, which
  has no password field. The log formatter never receives request bodies.
- **No account enumeration.** Login gives the same 401 `invalid_credentials` for an unknown
  email and a wrong password. Registration of an existing email gives 409; this is a
  deliberate usability trade-off, and the endpoint is rate-limited.

## Tokens

| Claim | Meaning |
|---|---|
| `sub` | User ID (UUID) |
| `jti` | Unique token ID, used for logout / revocation |
| `iat`, `exp` | Issued at and expiry (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 60) |
| `type` | `access`, so another kind of token can't be used as an access token |

- Signed with **HMAC-SHA256** using `JWT_SECRET_KEY`. In production the app refuses to start
  if the key is shorter than 32 characters. In development a temporary random key is used,
  with a warning.
- `alg=none`, forged signatures, wrong types and expired tokens are all rejected (tests in
  [`test_security.py`](../tests/test_security.py) and [`test_auth.py`](../tests/test_auth.py)).
- **Storage in the browser**: the token lives in `localStorage` and is sent in the
  `Authorization` header, never in cookies. This makes CSRF impossible by design. The trade-off
  is XSS exposure, which is mitigated by React's escaping and a strict CSP (`script-src 'self'`).
- **Logout** revokes server-side, then clears the token client-side. A 401 anywhere logs the
  user out of the UI.

## Protected dashboard (frontend)

[`RouteGuards.jsx`](../frontend/src/components/RouteGuards.jsx): `ProtectedRoute` redirects
anonymous users to `/login` and remembers where they were going. `PublicOnlyRoute` sends
signed-in users away from `/login` and `/register`. These guards are for UX only; **the API
is the real security boundary**.

## User isolation

- The user ID always comes from the verified token, never from a URL, query or body.
- Every repository query includes `user_id = :current_user`, for example
  `select(DietPlan).where(DietPlan.id == plan_id, DietPlan.user_id == user_id)`.
- A missing row and someone else's row give the same **404**. IDs are random UUIDs.
- Files: metadata ownership is checked before the object key is ever used.
- **TC-18** has 11 tests. Bob tries Alice's plan and file IDs on get, delete, export,
  save-to-cloud, download and delete-file: all 404, his lists are empty, and Alice's data is
  unchanged. A mutation check (removing the filter) makes 9 of them fail.

## Rate limiting

A sliding-window limiter ([`rate_limiter.py`](../backend/utils/rate_limiter.py)) allows
`RATE_LIMIT_AUTH_PER_MINUTE` (10) login and registration attempts per client and
`RATE_LIMIT_GENERATE_PER_MINUTE` (20) plan generations per user. When exceeded, it returns
**429** with `Retry-After`. Behind a proxy, set `TRUST_PROXY_HEADERS=true` so the real
client IP (`X-Forwarded-For`) is used.

## Moving to a managed identity provider

To use Supabase Auth, Firebase Auth, Cognito or Auth0, the frontend would get tokens from
the provider, and `get_current_user` would verify them with the provider's public keys
(JWKS, RS256) instead of `JWT_SECRET_KEY`. Services and isolation rules stay the same,
because they depend only on `CurrentUser`.
