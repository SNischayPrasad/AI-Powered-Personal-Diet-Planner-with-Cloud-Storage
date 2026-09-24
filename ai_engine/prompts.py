"""Prompt construction for the optional LLM provider.

Design choices
--------------
* **Numbers come from formulas, not from the model.** The calorie target and per-meal budgets
  are computed by ``nutrition.compute_targets`` and handed to the model as constraints; the
  model only proposes dishes. Totals are recomputed from its answer afterwards.
* **Data minimisation.** Only enumerated preferences and computed targets are sent — no name,
  email, age, height or weight. Because every value is from a fixed list, users cannot inject
  instructions into the prompt either.
* **Structured output.** The response must match ``MEAL_PLAN_JSON_SCHEMA`` exactly.
"""

import json

from ai_engine.nutrition import NutritionTargets, PlanRequest

MEAL_SLOTS = ("breakfast", "lunch", "snack", "dinner")

SYSTEM_PROMPT = """\
You are the meal-suggestion component of an educational diet-planning demo app. You propose \
one day of example meals (breakfast, lunch, snack and dinner) for the preferences you are \
given as structured data.

Rules:
- Follow the dietary preference strictly. "vegetarian" means no meat, poultry, fish, seafood \
or eggs (dairy is fine). "vegan" means no animal products at all: no meat, fish, eggs, dairy, \
ghee or honey. "non_vegetarian" allows everything.
- Never include a listed allergen in any form. For example "gluten" excludes wheat, barley, \
rye, semolina and regular soy sauce; "tree_nuts" excludes almonds, cashews and walnuts; \
"sesame" excludes tahini and hummus.
- Keep each meal close to its calorie budget (within about 15%).
- Suggest everyday, affordable, home-style dishes, in the requested cuisine when one is given.
- Give portions in household measures (bowls, cups, pieces) and approximate nutrition values \
that are consistent: 4 kcal per gram of protein or carbohydrate and 9 kcal per gram of fat.
- In "why", explain in one short sentence how the dish fits the preferences.
- This is general-wellness content for a demo, not medical advice: no diagnoses, supplements, \
medications or claims about treating conditions.
"""

_MEAL_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "portion": {"type": "string"},
        "ingredients": {"type": "array", "items": {"type": "string"}},
        "calories": {"type": "integer"},
        "protein_g": {"type": "number"},
        "carbs_g": {"type": "number"},
        "fat_g": {"type": "number"},
        "fiber_g": {"type": "number"},
        "why": {"type": "string"},
    },
    "required": ["name", "description", "portion", "ingredients", "calories", "protein_g",
                 "carbs_g", "fat_g", "fiber_g", "why"],
    "additionalProperties": False,
}

MEAL_PLAN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        **{slot: _MEAL_SCHEMA for slot in MEAL_SLOTS},
        "tips": {"type": "array", "items": {"type": "string"}},
    },
    "required": [*MEAL_SLOTS, "tips"],
    "additionalProperties": False,
}


def build_user_prompt(request: PlanRequest, targets: NutritionTargets) -> str:
    payload = {
        "dietary_preference": request.dietary_preference.value,
        "goal": request.goal.value,
        "cuisine": request.cuisine.value,
        "allergies_to_exclude": sorted(allergen.value for allergen in request.allergies),
        "daily_calorie_target": targets.calories,
        "macro_targets_g": {
            "protein": targets.protein_g,
            "carbs": targets.carbs_g,
            "fat": targets.fat_g,
        },
        "meal_calorie_budgets": targets.meal_calories,
    }
    return "Plan today's example meals for these preferences:\n" + json.dumps(payload, indent=2)


def schema_instructions() -> str:
    """For providers without schema-enforced output: describe the expected JSON in words."""
    example_meal = {
        "name": "…",
        "description": "…",
        "portion": "…",
        "ingredients": ["…"],
        "calories": 0,
        "protein_g": 0,
        "carbs_g": 0,
        "fat_g": 0,
        "fiber_g": 0,
        "why": "…",
    }
    example = {**{slot: example_meal for slot in MEAL_SLOTS}, "tips": ["…"]}
    return (
        "Respond with a single JSON object and nothing else, shaped exactly like this "
        "(every field required, numbers as numbers):\n" + json.dumps(example, ensure_ascii=False)
    )
