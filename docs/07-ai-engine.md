# 07 · AI diet recommendation engine

```text
PlanRequest ─► compute_targets() ─► LLM provider ─► validate ─► AI plan
  (enums +        (formulas)             │ error          │ rejected
   numbers)                              └──────► rule-based engine ─► plan (+ fallback_reason)
```

Code: [`ai_engine/`](../ai_engine). The planner is created once per app in
[`backend/app.py`](../backend/app.py) from `AI_PROVIDER`.

## Step 1: nutrition targets (shared by both versions)

[`nutrition.py`](../ai_engine/nutrition.py) turns the profile into numbers. The model never
invents them.

| Step | Formula |
|---|---|
| BMR (Mifflin-St Jeor) | `10·kg + 6.25·cm − 5·age + s`, with s = +5 (male), −161 (female), −78 (unspecified, the midpoint) |
| TDEE | BMR × activity factor: 1.2 / 1.375 / 1.55 / 1.725 / 1.9 |
| Calorie target | TDEE × goal factor: balanced 1.0, weight management 0.85, fitness 1.10; clamped to 1,200–4,000 kcal and rounded to 10 |
| Macros | Protein / carbs / fat share: balanced 20/50/30, weight management 30/40/30, fitness 30/45/25 (4, 4 and 9 kcal per gram) |
| Meal budgets | Breakfast 25%, lunch 35%, snack 10%, dinner 30% |
| Water | 35 ml/kg (+0.5 L if very or extra active), 1.5–4.5 L |

Worked example (TC-07): female, 28 years, 165 cm, 60 kg, moderately active, balanced →
BMR = 600 + 1,031.25 − 140 − 161 = 1,330.25. TDEE = 1,330.25 × 1.55 = 2,061.9, so the
target is **2,060 kcal**.

## Version A: rule-based recommendation engine

[`diet_engine.py`](../ai_engine/diet_engine.py) over
[`food_data.json`](../ai_engine/food_data.json), which holds 65 dishes. Each dish has its
meal slots, diet tags, allergens, cuisine, ingredients, nutrition per serving and a
portion description.

1. **Filter**: dishes for this slot whose diet tag fits (vegan ⊂ vegetarian ⊂ general) and
   that contain none of the user's allergens. These are hard rules. The chosen cuisine is
   *preferred* when at least two dishes in it remain; otherwise every cuisine is allowed.
2. **Scale** each candidate in quarter-serving steps (0.5×–2×) toward the meal's calorie
   budget.
3. **Score**: distance from the budget, plus a goal bonus (protein for fitness; fibre and
   protein for weight management; balanced macros otherwise).
4. **Pick** randomly among the top 3, so repeated plans vary while staying on target. The
   same dish is not reused within a day.
5. **Assemble**: totals vs. targets, the hydration tip, goal-specific tips, the disclaimer,
   and `source = "rule_based"`.

Why it counts as "AI": it is a knowledge-based recommender. Explicit rules and a scoring
function stand in for a learned model. It is transparent, deterministic in its constraints,
free, and works offline.

## Version B: optional LLM

Configure `AI_PROVIDER=anthropic` (Claude, via the official SDK) or
`AI_PROVIDER=openai_compatible` (Gemini, Groq, Ollama and others, via plain HTTPS), with keys
from environment variables only. See [`llm_providers.py`](../ai_engine/llm_providers.py).

### Prompt construction ([`prompts.py`](../ai_engine/prompts.py))

- **System prompt**: the model is the meal-suggestion part of an *educational* demo. It must
  follow the diet strictly, never include listed allergens (with examples such as "gluten
  excludes semolina"), stay near each meal's budget, keep macros consistent at 4/4/9 kcal per
  gram, use household portions, and give no diagnoses, supplements or medical claims.
- **User prompt**: a JSON object with only enumerated values and computed numbers:

  ```json
  {
    "dietary_preference": "vegetarian",
    "goal": "balanced",
    "cuisine": "indian",
    "allergies_to_exclude": ["peanuts"],
    "daily_calorie_target": 2060,
    "macro_targets_g": {"protein": 103, "carbs": 258, "fat": 69},
    "meal_calorie_budgets": {"breakfast": 515, "lunch": 721, "snack": 206, "dinner": 618}
  }
  ```

- **Data minimisation**: no name, email, age, height or weight leaves the server.
- **No prompt injection**: every value comes from a fixed list, so a user cannot smuggle
  instructions into the prompt.

### API request

- **Claude**: `messages.create` with structured output. The response must match
  `MEAL_PLAN_JSON_SCHEMA` (four meals and tips, `additionalProperties: false`). An `effort`
  setting keeps latency and cost low, and server-side refusal fallbacks are enabled on
  models that support them.
- **OpenAI-compatible**: `POST {base}/chat/completions` with `response_format` JSON and the
  schema described in the prompt.
- A timeout comes from `AI_TIMEOUT_SECONDS` (45 s by default).

### Response validation ([`validation.py`](../ai_engine/validation.py))

An answer is used only if it passes **every** check:

1. Valid JSON (a Markdown code fence is tolerated).
2. The structure matches, with realistic ranges (e.g. 30–2,500 kcal per meal and at least
   one ingredient).
3. **Diet**: no forbidden ingredient for the preference, using keyword lists such as
   *chicken, fish, egg, ghee, paneer* (the last two for vegans).
4. **Allergens**: none of the user's allergens, using keyword lists per allergen.
5. **Consistency**: each meal's calories agree with its macros within 35%.
6. **Total**: the day's calories are within ±20% of the target.

Known plant-based and gluten-free phrases ("oat milk", "peanut butter" (not dairy),
"jowar roti", "rice noodles"…) are removed before scanning to avoid false alarms. The checks lean toward
rejecting: a false rejection only means the rule engine answers instead.

Totals are **recomputed** from the validated meals. The model's own arithmetic is never
trusted.

### Error handling

| Failure | `fallback_reason` |
|---|---|
| AI disabled for this plan by the user | `ai_disabled` |
| AI requested but no key or model configured | `ai_not_configured` |
| SDK not installed | `sdk_missing` |
| Wrong or expired key; not permitted | `authentication_failed`, `permission_denied` |
| 429 from the provider | `rate_limited` |
| Timeout; DNS or connection failure | `timeout`, `network_error` |
| Other HTTP error from the provider (e.g. 500, 529 overloaded) | `api_error_<status>`, e.g. `api_error_529` |
| Malformed provider response body | `invalid_response` |
| Model refused; output cut off; empty | `refused`, `truncated`, `empty_response` |
| Not JSON / wrong shape | `invalid_json`, `invalid_schema` |
| Guardrail rejected the plan | `diet_violation`, `allergen_violation`, `inconsistent_nutrition`, `calorie_mismatch` |

### Fallback logic ([`planner.py`](../ai_engine/planner.py))

```python
try:
    return self._generate_with_ai(request, targets)
except (AIProviderError, AIValidationError) as exc:
    reason = exc.reason
    logger.warning("AI plan unavailable (%s); falling back to rules", exc)
plan = self.rule_engine.generate(request, targets)
return plan.model_copy(update={"fallback_reason": reason})
```

- The user always gets a plan. The API returns 201, not an error.
- The plan page shows a badge, e.g. *Rule-based engine: used because the AI provider could
  not be reached*.
- The `ai_fallbacks_total{reason=…}` metric and a warning log make outages visible to
  operators.
- Tests: TC-11 (6 provider failures) and TC-12 (not configured, disabled, and 9 guardrail
  cases), in [`tests/test_ai_fallback.py`](../tests/test_ai_fallback.py) and
  [`tests/test_llm_providers.py`](../tests/test_llm_providers.py).

## API keys

Keys are read from `ANTHROPIC_API_KEY` / `OPENAI_COMPAT_API_KEY`. They are never logged,
never returned by `/api/system/status` (which shows only the provider and model), never sent
to the browser, and `.env` is gitignored. With no key the app works fully on the rule-based
engine.
