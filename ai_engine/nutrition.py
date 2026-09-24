"""Nutrition maths used by every plan (rule-based *and* AI-generated).

Pipeline:  BMR (Mifflin-St Jeor)  ->  TDEE (x activity factor)  ->  goal adjustment
           ->  macro split  ->  per-meal calorie budget  ->  hydration estimate

The numbers are population-level *estimates* for healthy adults, used here for an
educational demo. They are not a medical assessment.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel

from ai_engine.options import ActivityLevel, Allergen, Cuisine, DietaryPreference, Goal, Sex

MEAL_SLOTS = ("breakfast", "lunch", "snack", "dinner")

# Share of the day's calories per meal.
MEAL_DISTRIBUTION = {"breakfast": 0.25, "lunch": 0.35, "snack": 0.10, "dinner": 0.30}

# Standard activity multipliers applied to BMR to estimate total daily energy expenditure.
ACTIVITY_MULTIPLIERS = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHTLY_ACTIVE: 1.375,
    ActivityLevel.MODERATELY_ACTIVE: 1.55,
    ActivityLevel.VERY_ACTIVE: 1.725,
    ActivityLevel.EXTRA_ACTIVE: 1.9,
}

# Gentle, general-wellness adjustments (a ~15% deficit / ~10% surplus).
GOAL_CALORIE_FACTORS = {
    Goal.BALANCED: 1.0,
    Goal.WEIGHT_MANAGEMENT: 0.85,
    Goal.FITNESS: 1.10,
}

# Share of calories from (protein, carbohydrate, fat).
MACRO_SPLITS = {
    Goal.BALANCED: (0.20, 0.50, 0.30),
    Goal.WEIGHT_MANAGEMENT: (0.30, 0.40, 0.30),
    Goal.FITNESS: (0.30, 0.45, 0.25),
}

# Mifflin-St Jeor sex constant; "unspecified" uses the midpoint of the two.
SEX_OFFSETS = {Sex.MALE: 5, Sex.FEMALE: -161, Sex.UNSPECIFIED: -78}

MIN_DAILY_CALORIES = 1200  # never suggest less than this without professional supervision
MAX_DAILY_CALORIES = 4000


@dataclass(frozen=True)
class PlanRequest:
    """Everything the planners need — and nothing else (no name, no email)."""

    age: int
    sex: Sex
    height_cm: float
    weight_kg: float
    activity_level: ActivityLevel
    dietary_preference: DietaryPreference
    goal: Goal
    allergies: frozenset[Allergen] = field(default_factory=frozenset)
    cuisine: Cuisine = Cuisine.ANY


class NutritionTargets(BaseModel):
    bmr: int
    tdee: int
    calories: int
    protein_g: int
    carbs_g: int
    fat_g: int
    macro_split: dict[str, int]  # percentages
    meal_calories: dict[str, int]
    water_liters: float


def mifflin_st_jeor_bmr(weight_kg: float, height_cm: float, age: int, sex: Sex) -> float:
    """Basal metabolic rate (kcal/day) — energy used at complete rest."""
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + SEX_OFFSETS[sex]


def hydration_liters(weight_kg: float, activity_level: ActivityLevel) -> float:
    """General guideline of ~35 ml per kg, plus 0.5 L for very active people, 1.5–4.5 L."""
    liters = weight_kg * 0.035
    if activity_level in (ActivityLevel.VERY_ACTIVE, ActivityLevel.EXTRA_ACTIVE):
        liters += 0.5
    return round(min(max(liters, 1.5), 4.5), 1)


def compute_targets(request: PlanRequest) -> NutritionTargets:
    bmr = mifflin_st_jeor_bmr(request.weight_kg, request.height_cm, request.age, request.sex)
    tdee = bmr * ACTIVITY_MULTIPLIERS[request.activity_level]
    calories = tdee * GOAL_CALORIE_FACTORS[request.goal]
    calories = min(max(calories, MIN_DAILY_CALORIES), MAX_DAILY_CALORIES)
    calories = int(round(calories / 10) * 10)

    protein_share, carbs_share, fat_share = MACRO_SPLITS[request.goal]
    return NutritionTargets(
        bmr=round(bmr),
        tdee=round(tdee),
        calories=calories,
        protein_g=round(calories * protein_share / 4),
        carbs_g=round(calories * carbs_share / 4),
        fat_g=round(calories * fat_share / 9),
        macro_split={
            "protein": round(protein_share * 100),
            "carbs": round(carbs_share * 100),
            "fat": round(fat_share * 100),
        },
        meal_calories={slot: round(calories * share) for slot, share in MEAL_DISTRIBUTION.items()},
        water_liters=hydration_liters(request.weight_kg, request.activity_level),
    )
