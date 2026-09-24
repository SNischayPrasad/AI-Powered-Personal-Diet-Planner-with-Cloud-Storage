"""Profile and plan options shared by the REST API and the AI engine.

Keeping every allowed value in one place means the API validation, the database, the
recommendation rules and the LLM prompt can never disagree about what "vegan" or
"fitness" means. Only these enumerated values ever reach the AI prompt — users cannot inject
free text into it.
"""

from enum import StrEnum


class Sex(StrEnum):
    FEMALE = "female"
    MALE = "male"
    UNSPECIFIED = "unspecified"  # the calorie estimate uses the midpoint of both formulas


class ActivityLevel(StrEnum):
    SEDENTARY = "sedentary"  # little or no exercise
    LIGHTLY_ACTIVE = "lightly_active"  # light exercise 1–3 days/week
    MODERATELY_ACTIVE = "moderately_active"  # moderate exercise 3–5 days/week
    VERY_ACTIVE = "very_active"  # hard exercise 6–7 days/week
    EXTRA_ACTIVE = "extra_active"  # physical job plus training


class DietaryPreference(StrEnum):
    VEGETARIAN = "vegetarian"  # lacto-vegetarian: no meat, fish or eggs
    VEGAN = "vegan"  # no animal products at all
    NON_VEGETARIAN = "non_vegetarian"  # general diet


class Goal(StrEnum):
    BALANCED = "balanced"  # general balanced eating
    WEIGHT_MANAGEMENT = "weight_management"  # weight-management demo
    FITNESS = "fitness"  # fitness-oriented demo


class Allergen(StrEnum):
    DAIRY = "dairy"
    EGG = "egg"
    GLUTEN = "gluten"
    PEANUTS = "peanuts"
    TREE_NUTS = "tree_nuts"
    SOY = "soy"
    FISH = "fish"
    SHELLFISH = "shellfish"
    SESAME = "sesame"


class Cuisine(StrEnum):
    ANY = "any"
    INDIAN = "indian"
    INTERNATIONAL = "international"


LABELS: dict[str, str] = {
    Sex.FEMALE: "Female",
    Sex.MALE: "Male",
    Sex.UNSPECIFIED: "Prefer not to say",
    ActivityLevel.SEDENTARY: "Sedentary",
    ActivityLevel.LIGHTLY_ACTIVE: "Lightly active",
    ActivityLevel.MODERATELY_ACTIVE: "Moderately active",
    ActivityLevel.VERY_ACTIVE: "Very active",
    ActivityLevel.EXTRA_ACTIVE: "Extra active",
    DietaryPreference.VEGETARIAN: "Vegetarian",
    DietaryPreference.VEGAN: "Vegan",
    DietaryPreference.NON_VEGETARIAN: "General / Non-vegetarian",
    Goal.BALANCED: "General balanced eating",
    Goal.WEIGHT_MANAGEMENT: "Weight-management demo",
    Goal.FITNESS: "Fitness-oriented demo",
    Allergen.DAIRY: "Dairy",
    Allergen.EGG: "Egg",
    Allergen.GLUTEN: "Gluten",
    Allergen.PEANUTS: "Peanuts",
    Allergen.TREE_NUTS: "Tree nuts",
    Allergen.SOY: "Soy",
    Allergen.FISH: "Fish",
    Allergen.SHELLFISH: "Shellfish",
    Allergen.SESAME: "Sesame",
    Cuisine.ANY: "Any cuisine",
    Cuisine.INDIAN: "Indian",
    Cuisine.INTERNATIONAL: "International",
}


def label(value: str) -> str:
    """Human-readable label for an option value (falls back to the value itself)."""
    return LABELS.get(value, value.replace("_", " ").capitalize())
