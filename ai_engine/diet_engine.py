"""Rule-based diet recommendation engine (the always-available "AI").

This is a classic knowledge-based system: a curated food dataset (the knowledge base) plus
transparent rules (the inference engine):

1. **Filter** dishes the user can eat — dietary preference and allergens are hard rules.
2. **Prefer** the chosen cuisine when enough dishes match.
3. **Scale** each dish in quarter-serving steps (0.5x–2x) towards the meal's calorie budget.
4. **Score** candidates: closeness to the budget, plus a goal-specific bonus
   (protein for fitness; fibre and protein for weight management; balanced macros otherwise).
5. **Pick** randomly among the three best-scoring dishes, so users get variety, and never
   repeat a dish within one plan.

It needs no internet connection, API key or GPU, which is why it doubles as the fallback
whenever the optional LLM provider is unavailable.
"""

import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ai_engine.nutrition import MEAL_SLOTS, NutritionTargets, PlanRequest, compute_targets
from ai_engine.options import Allergen, Cuisine, DietaryPreference, Goal, label

FOOD_DATA_PATH = Path(__file__).with_name("food_data.json")

DISCLAIMER = (
    "Educational, general-wellness example produced by a demo application. It is not medical "
    "or clinical nutrition advice and does not diagnose, treat or prevent any condition. "
    "Consult a qualified healthcare professional or registered dietitian before changing your "
    "diet, especially if you have a medical condition, are pregnant or have food allergies."
)

MIN_SERVINGS, MAX_SERVINGS = 0.5, 2.0
TOP_CHOICES = 3

# Which dataset diet classes each preference may eat.
ALLOWED_DIETS = {
    DietaryPreference.VEGAN: {"vegan"},
    DietaryPreference.VEGETARIAN: {"vegan", "vegetarian"},
    DietaryPreference.NON_VEGETARIAN: {"vegan", "vegetarian", "non_vegetarian"},
}

GOAL_TIPS = {
    Goal.BALANCED: [
        "Fill half your plate with vegetables or fruit at lunch and dinner.",
        "Choose whole grains such as brown rice, millets or whole-wheat roti when you can.",
        "Include a protein source (dal, beans, paneer, tofu, eggs, fish or chicken) in each "
        "main meal, as your diet allows.",
    ],
    Goal.WEIGHT_MANAGEMENT: [
        "Eat slowly and stop when you feel comfortably full.",
        "High-fibre foods such as vegetables, legumes and whole grains help you stay full.",
        "Limit sugary drinks and deep-fried snacks; keep regular meal times.",
    ],
    Goal.FITNESS: [
        "Spread protein across the day instead of eating it all at once.",
        "A carbohydrate-plus-protein snack 1-2 hours before training can help energy levels.",
        "Rehydrate after exercise, especially in hot weather.",
    ],
}


class FoodItem(BaseModel):
    id: str
    name: str
    description: str
    meal_types: list[Literal["breakfast", "lunch", "snack", "dinner"]]
    diet: Literal["vegan", "vegetarian", "non_vegetarian"]
    cuisine: Literal["indian", "international"]
    allergens: list[Allergen] = []
    portion: str
    ingredients: list[str]
    calories: int = Field(gt=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    fiber_g: float = Field(ge=0)


class Meal(BaseModel):
    food_id: str | None = None  # dataset id for rule-based meals; None for AI meals
    name: str
    description: str
    portion: str
    servings: float = 1.0
    ingredients: list[str]
    calories: int
    protein_g: int
    carbs_g: int
    fat_g: int
    fiber_g: int
    diet: str
    cuisine: str
    allergens: list[str] = []
    why: str = ""


class NutritionTotals(BaseModel):
    calories: int
    protein_g: int
    carbs_g: int
    fat_g: int
    fiber_g: int


class GeneratedPlan(BaseModel):
    title: str
    dietary_preference: str
    goal: str
    cuisine: str
    allergies: list[str]
    meals: dict[str, Meal]
    targets: NutritionTargets
    totals: NutritionTotals
    macro_percentages: dict[str, int]
    hydration_tip: str
    tips: list[str]
    source: Literal["rule_based", "ai"] = "rule_based"
    ai_provider: str | None = None
    ai_model: str | None = None
    fallback_reason: str | None = None
    disclaimer: str = DISCLAIMER


class NoSuitableMealsError(Exception):
    """No dish satisfies the user's diet and allergy restrictions for a meal slot."""

    def __init__(self, slot: str) -> None:
        self.slot = slot
        super().__init__(
            f"No {slot} options match your dietary preference and allergies. "
            "Try removing an allergy filter or choosing a different dietary preference."
        )


@lru_cache(maxsize=4)
def _load_foods_cached(path: str) -> tuple[FoodItem, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(FoodItem.model_validate(item) for item in raw["foods"])


def load_foods(path: Path = FOOD_DATA_PATH) -> list[FoodItem]:
    """Load and validate the food dataset (cached after the first call)."""
    return list(_load_foods_cached(str(path)))


def _round_to_quarter(value: float) -> float:
    return round(value * 4) / 4


def build_hydration_tip(water_liters: float) -> str:
    glasses = round(water_liters / 0.25)
    return (
        f"Aim for roughly {water_liters:.1f} L of fluids across the day (about {glasses} glasses "
        "of 250 ml), and more in hot weather or when you exercise. Water is best; unsweetened "
        "drinks such as lemon water or herbal tea also count. Individual needs vary."
    )


def assemble_plan(
    request: PlanRequest,
    targets: NutritionTargets,
    meals: dict[str, Meal],
    *,
    source: Literal["rule_based", "ai"] = "rule_based",
    ai_provider: str | None = None,
    ai_model: str | None = None,
    fallback_reason: str | None = None,
    extra_tips: list[str] | None = None,
) -> GeneratedPlan:
    """Build the final plan from four meals. Totals are always recomputed here from the meals
    themselves — never trusted from an external source such as an LLM."""
    totals = NutritionTotals(
        calories=sum(meal.calories for meal in meals.values()),
        protein_g=sum(meal.protein_g for meal in meals.values()),
        carbs_g=sum(meal.carbs_g for meal in meals.values()),
        fat_g=sum(meal.fat_g for meal in meals.values()),
        fiber_g=sum(meal.fiber_g for meal in meals.values()),
    )
    energy = {"protein": totals.protein_g * 4, "carbs": totals.carbs_g * 4,
              "fat": totals.fat_g * 9}
    energy_total = sum(energy.values()) or 1
    macro_percentages = {key: round(value * 100 / energy_total) for key, value in energy.items()}

    tips = list(GOAL_TIPS[request.goal])
    if request.allergies:
        tips.append("Always check ingredient labels for your listed allergens; recipes and "
                    "brands vary.")
    tips.extend(extra_tips or [])

    title = (f"{label(request.dietary_preference)} · {label(request.goal)} · "
             f"{targets.calories:,} kcal/day")
    return GeneratedPlan(
        title=title,
        dietary_preference=request.dietary_preference.value,
        goal=request.goal.value,
        cuisine=request.cuisine.value,
        allergies=sorted(allergen.value for allergen in request.allergies),
        meals=meals,
        targets=targets,
        totals=totals,
        macro_percentages=macro_percentages,
        hydration_tip=build_hydration_tip(targets.water_liters),
        tips=tips,
        source=source,
        ai_provider=ai_provider,
        ai_model=ai_model,
        fallback_reason=fallback_reason,
    )


class RuleBasedDietEngine:
    """Deterministic when given a seeded ``random.Random`` (used by the tests)."""

    name = "rule_based"

    def __init__(self, foods: list[FoodItem] | None = None,
                 rng: random.Random | None = None) -> None:
        self.foods = foods if foods is not None else load_foods()
        self.rng = rng or random.Random()  # noqa: S311 — variety, not security

    def candidates(self, slot: str, request: PlanRequest) -> list[FoodItem]:
        """Dishes for ``slot`` that respect the user's diet and allergies (hard rules)."""
        allowed_diets = ALLOWED_DIETS[request.dietary_preference]
        return [
            food
            for food in self.foods
            if slot in food.meal_types
            and food.diet in allowed_diets
            and not set(food.allergens) & request.allergies
        ]

    def _score(self, food: FoodItem, budget: int, goal: Goal) -> tuple[float, float]:
        servings = min(max(_round_to_quarter(budget / food.calories), MIN_SERVINGS),
                       MAX_SERVINGS)
        calorie_error = abs(food.calories * servings - budget) / budget
        protein_ratio = food.protein_g * 4 / food.calories
        carbs_ratio = food.carbs_g * 4 / food.calories
        fiber_per_100kcal = food.fiber_g * 100 / food.calories

        if goal == Goal.FITNESS:
            bonus = 0.15 * min(protein_ratio / 0.30, 1)
        elif goal == Goal.WEIGHT_MANAGEMENT:
            bonus = 0.12 * min(protein_ratio / 0.30, 1) + 0.06 * min(fiber_per_100kcal / 3, 1)
        else:
            imbalance = abs(protein_ratio - 0.20) + abs(carbs_ratio - 0.50)
            bonus = 0.10 * (1 - min(imbalance, 1))
        return calorie_error - bonus, servings

    @staticmethod
    def _why(food: FoodItem, goal: Goal, servings: float, slot: str) -> str:
        """Explain the pick in plain language: facts about the dish + how it fits the goal."""
        facts = []
        if food.protein_g * 4 / food.calories >= 0.2:
            facts.append("good source of protein")
        if food.fiber_g * 100 / food.calories >= 2:
            facts.append("rich in fibre")
        if food.fat_g * 9 / food.calories <= 0.2:
            facts.append("low in fat")
        goal_reason = {
            Goal.FITNESS: "Supports your training.",
            Goal.WEIGHT_MANAGEMENT: "Filling while staying within your calorie budget.",
            Goal.BALANCED: "Adds steady, balanced energy to your day.",
        }[goal]
        lead = ", ".join(facts) if facts else "balanced mix of carbohydrates, protein and fat"
        reason = f"{lead[0].upper()}{lead[1:]}. {goal_reason}"
        if servings != 1:
            reason += f" Portion set to {servings:g} servings to fit your {slot} budget."
        return reason

    def _pick(self, slot: str, request: PlanRequest, budget: int,
              used_ids: set[str]) -> Meal:
        pool = [food for food in self.candidates(slot, request) if food.id not in used_ids]
        if not pool:
            raise NoSuitableMealsError(slot)
        if request.cuisine != Cuisine.ANY:
            preferred = [food for food in pool if food.cuisine == request.cuisine]
            if len(preferred) >= 2:
                pool = preferred

        ranked = sorted(pool, key=lambda food: self._score(food, budget, request.goal)[0])
        food = self.rng.choice(ranked[:TOP_CHOICES])
        _, servings = self._score(food, budget, request.goal)
        used_ids.add(food.id)
        return Meal(
            food_id=food.id,
            name=food.name,
            description=food.description,
            portion=food.portion,
            servings=servings,
            ingredients=list(food.ingredients),
            calories=round(food.calories * servings),
            protein_g=round(food.protein_g * servings),
            carbs_g=round(food.carbs_g * servings),
            fat_g=round(food.fat_g * servings),
            fiber_g=round(food.fiber_g * servings),
            diet=food.diet,
            cuisine=food.cuisine,
            allergens=[allergen.value for allergen in food.allergens],
            why=self._why(food, request.goal, servings, slot),
        )

    def generate(self, request: PlanRequest,
                 targets: NutritionTargets | None = None) -> GeneratedPlan:
        targets = targets or compute_targets(request)
        used_ids: set[str] = set()
        meals = {
            slot: self._pick(slot, request, targets.meal_calories[slot], used_ids)
            for slot in MEAL_SLOTS
        }
        return assemble_plan(request, targets, meals)
