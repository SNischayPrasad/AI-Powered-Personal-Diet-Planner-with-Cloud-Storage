"""Guardrails for LLM answers. An AI answer is only used when it passes every check:

1. it is valid JSON (optionally wrapped in a Markdown code fence);
2. it matches the expected structure, with values in realistic ranges;
3. no dish contains an ingredient the dietary preference forbids;
4. no dish contains one of the user's allergens;
5. each meal's calories agree with its macros (4/4/9 kcal per gram);
6. the day's total is within 20% of the calorie target.

Anything else raises ``AIValidationError`` and the planner falls back to the rule-based engine.

The diet and allergen checks are keyword heuristics — a safety net, not a guarantee — and they
err on the side of rejecting. Known plant-based and gluten-free phrases ("oat milk",
"peanut butter", "jowar roti", "rice noodles"…) are removed before scanning so they don't
trigger false alarms.
"""

import json
import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ai_engine.diet_engine import Meal
from ai_engine.nutrition import MEAL_SLOTS, NutritionTargets, PlanRequest
from ai_engine.options import Allergen, Cuisine, DietaryPreference

DAILY_CALORIE_TOLERANCE = 0.20
MACRO_CONSISTENCY_TOLERANCE = 0.35


class AIValidationError(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


class AIMeal(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=400)
    portion: str = Field(min_length=1, max_length=120)
    ingredients: list[str] = Field(min_length=1, max_length=20)
    calories: int = Field(ge=30, le=2500)
    protein_g: float = Field(ge=0, le=250)
    carbs_g: float = Field(ge=0, le=400)
    fat_g: float = Field(ge=0, le=200)
    fiber_g: float = Field(ge=0, le=80)
    why: str = Field(default="", max_length=300)

    @field_validator("ingredients")
    @classmethod
    def _clean_ingredients(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip()[:80] for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("at least one ingredient is required")
        return cleaned


class AIMealPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    breakfast: AIMeal
    lunch: AIMeal
    snack: AIMeal
    dinner: AIMeal
    tips: list[str] = Field(default_factory=list, max_length=8)


# --- Vocabulary ---------------------------------------------------------------------------------
MEAT = ["chicken", "mutton", "lamb", "beef", "pork", "bacon", "ham", "turkey", "goat", "veal",
        "duck", "sausage", "salami", "pepperoni", "keema", "meat", "venison", "gelatin",
        "gelatine", "lard"]
FISH = ["fish", "salmon", "tuna", "sardine", "mackerel", "anchovy", "anchovies", "cod",
        "tilapia", "trout", "hilsa", "rohu", "pomfret", "fish sauce"]
SHELLFISH = ["prawn", "shrimp", "crab", "lobster", "mussel", "oyster", "clam", "scallop",
             "squid", "crayfish"]
EGG = ["egg", "omelette", "omelet", "mayonnaise", "mayo", "meringue"]
DAIRY = ["milk", "paneer", "cheese", "butter", "ghee", "yogurt", "yoghurt", "curd", "cream",
         "buttermilk", "whey", "khoa", "khoya", "dahi", "lassi", "chaas", "kefir"]
HONEY = ["honey"]

DIET_FORBIDDEN = {
    DietaryPreference.VEGETARIAN: MEAT + FISH + SHELLFISH + EGG,
    DietaryPreference.VEGAN: MEAT + FISH + SHELLFISH + EGG + DAIRY + HONEY,
    DietaryPreference.NON_VEGETARIAN: [],
}

ALLERGEN_TERMS = {
    Allergen.DAIRY: DAIRY,
    Allergen.EGG: EGG,
    Allergen.GLUTEN: ["wheat", "barley", "rye", "semolina", "rava", "sooji", "suji", "maida",
                      "atta", "bread", "pasta", "noodle", "couscous", "bulgur", "seitan", "roti",
                      "chapati", "paratha", "naan", "soy sauce", "cracker", "tortilla",
                      "spaghetti", "macaroni", "pita", "bun", "biscuit", "oats", "oatmeal",
                      "muesli", "granola", "dalia", "bagel", "croissant", "multigrain"],
    Allergen.PEANUTS: ["peanut", "groundnut", "moongphali"],
    Allergen.TREE_NUTS: ["almond", "cashew", "walnut", "pistachio", "hazelnut", "pecan",
                         "macadamia", "brazil nut", "pine nut", "mixed nuts", "badam", "kaju",
                         "akhrot", "praline", "marzipan"],
    Allergen.SOY: ["soy", "soya", "soybean", "tofu", "edamame", "tempeh", "miso", "tamari"],
    Allergen.FISH: FISH,
    Allergen.SHELLFISH: SHELLFISH,
    Allergen.SESAME: ["sesame", "tahini", "til", "gingelly", "hummus"],
}

# Phrases that contain a forbidden word but are fine (removed before scanning).
PLANT_BASED_PHRASES = [
    r"\b(?:almond|soy|soya|oat|coconut|rice|cashew|peanut|hemp|pea|plant[- ]based|vegan|"
    r"dairy[- ]free)\s+(?:milk|yogurt|yoghurt|curd|cheese|butter|cream|ghee)s?\b",
    r"\b(?:peanut|almond|cashew|nut|seed|sunflower|sesame|cocoa|shea|apple)\s+butter\b",
    r"\bbutter\s?nut\b",
    r"\bbutter\s+beans?\b",
    r"\bbean\s+curd\b",
    r"\b(?:mock|soy|soya|plant[- ]based|vegan|jackfruit)\s+meat\b",
    r"\bcream\s+of\s+tartar\b",
    r"\begg[- ]?(?:free|less)\b",
    r"\bflax\s+eggs?\b",
]
GLUTEN_FREE_PHRASES = [
    r"\bgluten[- ]free\s+[a-z]+\b",
    r"\b(?:jowar|bajra|ragi|rice|corn|maize|makki|millet|buckwheat|kuttu|sorghum|quinoa|"
    r"chickpea|besan|gram|amaranth|rajgira|tapioca|sabudana)\s+(?:rotis?|flour|atta|noodles?|"
    r"breads?|pasta|dosas?|chillas?|wraps?|tortillas?|flatbreads?|crackers?)\b",
]


def _without(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        text = re.sub(pattern, " ", text)
    return text


def _find_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if re.search(rf"\b{re.escape(term)}(?:e?s)?\b", text)]


def _meal_text(meal: AIMeal) -> str:
    return " ".join([meal.name, meal.description, meal.portion, *meal.ingredients]).lower()


def _strip_code_fence(raw: str) -> str:
    text = raw.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else text


def parse_ai_plan(raw: str) -> AIMealPlan:
    try:
        data = json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError as exc:
        raise AIValidationError("invalid_json", str(exc)) from exc
    try:
        return AIMealPlan.model_validate(data)
    except ValidationError as exc:
        raise AIValidationError("invalid_schema", f"{exc.error_count()} problem(s)") from exc


def check_plan(plan: AIMealPlan, request: PlanRequest, targets: NutritionTargets) -> None:
    diet_terms = DIET_FORBIDDEN[request.dietary_preference]
    for slot in MEAL_SLOTS:
        meal: AIMeal = getattr(plan, slot)
        text = _meal_text(meal)

        found = _find_terms(_without(text, PLANT_BASED_PHRASES), diet_terms)
        if found:
            raise AIValidationError("diet_violation", f"{slot}: {', '.join(found)}")

        for allergen in request.allergies:
            safe = PLANT_BASED_PHRASES if allergen in (Allergen.DAIRY, Allergen.EGG) else []
            if allergen == Allergen.GLUTEN:
                safe = GLUTEN_FREE_PHRASES
            found = _find_terms(_without(text, safe), ALLERGEN_TERMS[allergen])
            if found:
                raise AIValidationError("allergen_violation",
                                        f"{slot}: {allergen.value} ({', '.join(found)})")

        from_macros = 4 * meal.protein_g + 4 * meal.carbs_g + 9 * meal.fat_g
        if abs(from_macros - meal.calories) / meal.calories > MACRO_CONSISTENCY_TOLERANCE:
            detail = f"{slot}: {meal.calories} kcal vs {from_macros:.0f} kcal from macros"
            raise AIValidationError("inconsistent_nutrition", detail)

    total = sum(getattr(plan, slot).calories for slot in MEAL_SLOTS)
    if abs(total - targets.calories) / targets.calories > DAILY_CALORIE_TOLERANCE:
        raise AIValidationError("calorie_mismatch", f"{total} kcal vs target {targets.calories}")


def to_meals(plan: AIMealPlan, request: PlanRequest) -> dict[str, Meal]:
    cuisine = request.cuisine.value if request.cuisine != Cuisine.ANY else "any"
    meals = {}
    for slot in MEAL_SLOTS:
        meal: AIMeal = getattr(plan, slot)
        meals[slot] = Meal(
            food_id=None,
            name=meal.name,
            description=meal.description,
            portion=meal.portion,
            servings=1.0,
            ingredients=meal.ingredients,
            calories=meal.calories,
            protein_g=round(meal.protein_g),
            carbs_g=round(meal.carbs_g),
            fat_g=round(meal.fat_g),
            fiber_g=round(meal.fiber_g),
            diet=request.dietary_preference.value,
            cuisine=cuisine,
            allergens=[],
            why=meal.why or "Suggested by the AI provider for your preferences.",
        )
    return meals


def validate_ai_plan(
    raw: str, request: PlanRequest, targets: NutritionTargets
) -> tuple[dict[str, Meal], list[str]]:
    """Parse and check an LLM answer. Returns (meals, extra tips) or raises AIValidationError."""
    plan = parse_ai_plan(raw)
    check_plan(plan, request, targets)
    tips = [tip.strip()[:200] for tip in plan.tips if tip and tip.strip()][:2]
    return to_meals(plan, request), tips
