# 16 · Testing strategy

Every requirement in the brief is covered by an automated test. The suites run on every push
through GitHub Actions ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)).

| Layer | Tool | What it proves | Count |
|---|---|---|---|
| Unit | pytest | Nutrition maths, rule engine, AI validation, security helpers, storage adapters | part of 293 |
| API / integration | pytest + FastAPI `TestClient` | Every endpoint through real HTTP, a real database and real object storage | part of 293 |
| Cloud adapters | pytest + `moto` | The S3 code path with the real boto3 calls against an in-memory S3 | 19 |
| AI adapters | pytest + mock HTTP transports | Claude (through the real `anthropic` SDK) and OpenAI-compatible request shapes and error mapping | 24 |
| Database portability | pytest with `TEST_DATABASE_URL` | The full suite on PostgreSQL as well as SQLite | 293 |
| Frontend unit | Vitest | Formatting, thali geometry, API client (errors, tokens, downloads) | 31 |
| End-to-end | [`scripts/smoke_test.py`](../scripts/smoke_test.py) | The whole user journey against a running deployment | 28 checks |
| Deployment | CI `docker` job + `tests/test_deployment.py` | The production image runs as non-root, serves the React app and passes the smoke test alone (SQLite) and with PostgreSQL + S3-compatible storage (RustFS) | 2 × 28 checks |

## How to run

```bash
# Backend (from the project root, virtual environment active)
pytest                       # all 293 tests, about a minute
pytest --cov                 # with a coverage report
pytest -k tc18               # a single test case family
ruff check .                 # lint, including security checks

# Same suite against PostgreSQL (any empty database you can reach)
TEST_DATABASE_URL=postgresql://user:password@localhost:5432/dietplanner_test pytest

# Frontend
cd frontend && npm test

# End-to-end against a running API (local or deployed)
python scripts/smoke_test.py --base-url http://localhost:8000
```

On Windows PowerShell, set the database variable with
`$env:TEST_DATABASE_URL = "postgresql://…"` before running `pytest`.

## Design choices

- **Isolation.** Each test gets a fresh temporary SQLite database and storage folder. With
  `TEST_DATABASE_URL`, every test starts from empty tables instead.
- **Real components, fake networks.** Tests use a real database, real object storage (a
  folder, or `moto`'s S3) and the real SDKs. Only the network edge is simulated: HTTP
  transports for the LLM providers.
- **Real failures instead of mocks where possible.** A database or storage *outage* is
  produced by putting a file where the database or bucket directory should be. The driver or
  filesystem then raises a genuine error.
- **Mutation checks.** For the most important guarantees, the protection was removed on
  purpose to confirm the tests fail:
  - Dropping the owner filter from plan and file lookups makes 9 of the 11 TC-18 tests fail.
  - Deleting the compensating object delete makes the orphan-cleanup test fail.
- **Hand-derived expectations.** Numbers such as the 2,060 kcal target are worked out by hand
  from the Mifflin-St Jeor equation, never computed with the code under test.

## Test cases

Actual results are from the runs on 24–25 September 2026:
- 293 passed on SQLite (Python 3.13); the PostgreSQL job in CI runs the same suite (266 also
  passed locally on PostgreSQL 18 before the later tests were added).
- 31 frontend tests passed.
- The smoke test passed 28 of 28 checks against the local stack.

| Test ID | Scenario | Input | Expected result | Actual result | Pass/Fail | Automated test |
|---|---|---|---|---|---|---|
| TC-01 | New user registration | Name, new email `Asha.Rao@Example.com`, strong password | 201, JWT returned, email stored lower-case, no password in the response | As expected | Pass | `test_tc01_register_new_user_returns_token_and_public_profile` |
| TC-02 | Existing email registration | Same email in different case | 409 `email_already_registered` | As expected | Pass | `test_tc02_register_with_existing_email_is_rejected_case_insensitively` |
| TC-03 | Valid login | Correct email + password | 200 and a token that works on a protected route | As expected | Pass | `test_tc03_login_with_valid_credentials_returns_a_working_token` |
| TC-04 | Invalid login | Wrong password; unknown email | 401 `invalid_credentials`, same message for both (no account enumeration) | As expected | Pass | `test_tc04_login_with_wrong_password_is_rejected`, `test_login_error_does_not_reveal_whether_an_email_is_registered` |
| TC-05 | Unauthorized dashboard access | No token, garbage token, forged or unsigned token, expired token | 401 with `WWW-Authenticate: Bearer` | As expected | Pass | `test_tc05_protected_endpoint_without_token_is_rejected`, `test_tc05_profile_requires_authentication`, forged/`alg=none`/expired token tests |
| TC-06 | Profile creation | Age 31, 72.5 kg, fitness, allergies | 200, values saved, `profile_complete` true; out-of-range values give 422 | As expected | Pass | `test_tc06_profile_is_saved_and_returned` + 11 validation cases |
| TC-07 | Diet plan generation | Complete profile | 201, four meals, nutrition summary (target 2,060 kcal), hydration tip, disclaimer | As expected | Pass | `test_tc07_generate_plan_returns_four_meals_nutrition_summary_and_disclaimer` |
| TC-08 | Vegetarian preference | Vegetarian profile, 10 random seeds | No meat, fish or eggs in any dish | As expected | Pass | `test_tc08_vegetarian_plan_contains_no_meat_fish_or_eggs`, `test_tc08_vegetarian_profile_gets_only_vegetarian_dishes` |
| TC-09 | Vegan preference | Vegan override, 10 random seeds | Only vegan dishes; the profile itself is unchanged | As expected | Pass | `test_tc09_vegan_plan_contains_no_animal_products`, `test_tc09_vegan_override_applies_to_this_plan_without_changing_the_profile` |
| TC-10 | Different goal | Weight management vs balanced vs fitness | 1,750 < 2,060 < 2,270 kcal; protein share 30% for fitness | As expected | Pass | `test_tc10_goal_changes_the_calorie_target_and_macro_split`, `test_tc10_weight_management_goal_lowers_the_calorie_target` |
| TC-11 | AI API failure | Provider raises timeout / rate limit / network / auth / refusal / HTTP 529 | Plan still generated by the rules, `fallback_reason` names the failure | As expected | Pass | `test_tc11_ai_provider_failures_fall_back_to_the_rule_based_engine` (6 cases) |
| TC-12 | Rule-based fallback | AI requested but not configured; AI switched off by the user; invalid or unsafe AI answers | Rule-based plan with the matching reason (`ai_not_configured`, `ai_disabled`, `diet_violation`…) | As expected | Pass | `test_tc12_ai_requested_but_not_configured_uses_the_rule_based_engine` + 9 guardrail cases |
| TC-13 | Save diet plan | Generate two plans | Both stored in the database, listed newest first | As expected | Pass | `test_tc13_generated_plans_are_saved_to_the_database_newest_first` |
| TC-14 | Retrieve plan | `GET /api/plans/{id}` | Identical to the plan returned at creation; unknown or malformed ids give 404 | As expected | Pass | `test_tc14_a_saved_plan_can_be_retrieved_by_id` |
| TC-15 | Upload file | `my lunch.png` (real PNG) | 201; object stored under `users/<id>/meal-images/<uuid>.png` | As expected | Pass | `test_tc15_meal_image_upload_is_stored_in_object_storage` |
| TC-16 | Retrieve file | List, then download | Listed with size; download is byte-for-byte identical | As expected | Pass | `test_tc16_uploaded_files_are_listed_and_download_byte_for_byte` |
| TC-17 | Invalid file | `.txt`, `.exe`, `.svg`, JPEG named `.png`, `photo.png.html`, empty, over 4 MB | 415 / 400 / 413 with a clear code; nothing stored | As expected | Pass | `test_tc17_invalid_files_are_rejected` (6 cases), `test_tc17_files_over_the_size_limit_are_rejected` |
| TC-18 | User A cannot retrieve User B's data | Bob requests Alice's plan and file IDs on 7 endpoints | 404 everywhere, lists empty, Alice's data untouched | As expected | Pass | `test_tc18_*` (11 tests) |
| TC-19 | Logout | Log out, then reuse the token | 200, then 401 `token_revoked`; other sessions keep working | As expected | Pass | `test_tc19_logout_revokes_the_token_server_side` |
| TC-20 | Cloud / database failure handling | Database unreachable; storage bucket unwritable; database fails after an upload | App stays up; readiness 503; requests 503 with `database_unavailable` / `storage_unavailable`; no orphaned objects; automatic recovery | As expected | Pass | `test_tc20_*` (3 tests), `test_service_recovers_when_the_database_comes_back`, `test_object_is_removed_again_when_its_metadata_cannot_be_saved` |

## Coverage

`pytest --cov` reports **97 %** statement coverage for `backend/`, `ai_engine/` and `cloud/`
(1,765 statements, 56 missed). The uncovered lines are mostly defensive branches: an S3
network failure while deleting, a missing SDK, and logging formatter internals.

## Manual checks in a real browser

The React app was driven in a browser against the running API.

| Journey | Result |
|---|---|
| Register → redirected to the profile form with a welcome message | Pass |
| Client-side validation (short password) shows an inline error | Pass |
| Save profile → success message and "Generate a plan" action | Pass |
| Generate plan → plan page with thali, meters, meals, hydration and tips | Pass |
| Save as text to cloud storage → appears in Cloud files | Pass |
| Drag-and-drop image upload → stored and shown as an authenticated preview | Pass |
| Dashboard at 1366 px and 375 px (mobile) | Pass |
| Log out → token revoked on the server (reuse returns 401) | Pass |
| Wrong password shows "Incorrect email or password." | Pass |
| Second user opening the first user's plan ID | 404 (Pass) |
| AI endpoint unreachable → "Rule-based engine: used because the AI provider could not be reached" | Pass |
| Production build served by FastAPI on one port: deep link reload, fonts under the strict CSP, register → profile → plan | Pass |
