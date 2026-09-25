# 02 · Features

## User registration and login

| Action | How it works | Code |
|---|---|---|
| Register | Name, email and password; the email is normalised to lower case. The password needs 8+ characters with a letter and a number, and at most 72 bytes (bcrypt's limit). Returns 201 and a token, so the user is signed in straight away | [`auth_service.py`](../backend/services/auth_service.py) |
| Login | The same "Incorrect email or password" message for either mistake, so attackers can't discover which emails exist. Rate-limited | [`auth_routes.py`](../backend/routes/auth_routes.py) |
| Logout | The token's ID is recorded as revoked, so it stops working at once (not only when it expires) | `POST /api/logout` |

## Profile (demo information only)

| Field | Allowed values |
|---|---|
| Name | 1–100 characters |
| Age | 18–90 |
| Sex | female, male, prefer not to say (uses the midpoint of the two formulas) |
| Height | 100–250 cm |
| Weight | 30–300 kg |
| Activity level | sedentary, lightly active, moderately active, very active, extra active |
| Dietary preference | vegetarian, vegan, general / non-vegetarian |
| Goal | general balanced eating, weight-management demo, fitness-oriented demo |
| Allergies (optional) | dairy, egg, gluten, peanuts, tree nuts, soy, fish, shellfish, sesame |
| Cuisine (optional) | any, Indian, international |

The app never asks for or infers medical conditions.

## Diet plan

Each plan contains:

- **Breakfast, lunch, snack and dinner**, each with a dish name, description, portion in
  household measures, ingredients, calories, protein, carbs, fat and fibre, and a "why this
  fits you" sentence.
- **Nutrition summary**: daily target vs. plan total for calories and each macro, plus the
  macro split.
- **Hydration reminder** based on body weight and activity (roughly 35 ml/kg, 1.5–4.5 L).
- **Tips** and a **disclaimer** that labels the plan as an educational, general-wellness
  example.
- **Provenance**: which engine produced it (AI or rule-based), the model, and why the AI was
  skipped when it was.

Plan types: vegetarian, vegan, general. Goals: balanced (maintenance calories), weight
management (about 15% below), fitness (about 10% above, more protein). On the Generate page
you can override diet, goal, allergies, cuisine or AI use **for one plan** without changing
the saved profile.

## Saved plans and cloud storage

- List plans newest first, open any plan, delete a plan.
- Export a plan as JSON or plain text (download).
- **Save to cloud**: store the export as a file in object storage.
- Upload meal images (JPEG, PNG, WebP) or PDFs of up to 4 MB, 50 files per user. Preview,
  download or delete them.

## Dashboard

"Welcome, *name*", current goal, diet preference, latest plan (as a thali), previous plans,
Generate New Plan, uploaded files, a live **cloud status** panel (database, storage and AI
provider, with readiness) and Logout.

## Pages

Landing · Register · Login · Profile · Generate plan · Plan result · Saved plans · Cloud
files · Dashboard · 404. See [10 · Frontend](10-frontend.md).

## Operational features

- `/api/health` (liveness), `/api/health/ready` (database and storage reachable),
  `/api/system/status` (which providers are active, no secrets).
- `/api/metrics` in Prometheus text format: requests, auth events, plans by engine, AI
  fallbacks, uploads, dependency errors.
- An `X-Request-ID` on every response and in every log line; JSON logs for the cloud.
- Rate limits on authentication and plan generation.
- Graceful degradation: if the database or storage is down, the app stays up, readiness
  reports it, and requests get a clear 503 until it recovers.
