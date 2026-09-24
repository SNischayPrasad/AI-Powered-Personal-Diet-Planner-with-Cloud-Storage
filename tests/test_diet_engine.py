"""Rule-based AI diet engine — TC-08 (vegetarian), TC-09 (vegan), TC-10 (different goal)
plus nutrition maths and food-dataset quality checks.

Expected numbers are worked out by hand from the Mifflin-St Jeor equation, e.g. for the
reference profile (female, 28 y, 165 cm, 60 kg):
    BMR  = 10*60 + 6.25*165 - 5*28 - 161      = 1330.25 kcal
    TDEE = 1330.25 * 1.55 (moderately active) = 2061.89 kcal
"""

import random
import re

import pytest

from ai_engine.diet_engine import (
    DISCLAIMER,
    FoodItem,
    NoSuitableMealsError,
    RuleBasedDietEngine,
    load_foods,
)
from ai_engine.nutrition import MEAL_SLOTS, PlanRequest, compute_targets, mifflin_st_jeor_bmr
from ai_engine.options import ActivityLevel, Allergen, Cuisine, DietaryPreference, Goal, Sex


def make_request(**overrides) -> PlanRequest:
    values = {
        "age": 28,
        "sex": Sex.FEMALE,
        "height_cm": 165,
        "weight_kg": 60,
        "activity_level": ActivityLevel.MODERATELY_ACTIVE,
        "dietary_preference": DietaryPreference.VEGETARIAN,
        "goal": Goal.BALANCED,
        "allergies": frozenset(),
        "cuisine": Cuisine.ANY,
    }
    values.update(overrides)
    return PlanRequest(**values)


def generate(seed: int = 7, **overrides):
    return RuleBasedDietEngine(rng=random.Random(seed)).generate(make_request(**overrides))


def meal_text(meal) -> str:
    return " ".join([meal.name, meal.description, *meal.ingredients]).lower()


def contains_word(text: str, words: list[str]) -> list[str]:
    return [w for w in words if re.search(rf"\b{re.escape(w)}s?\b", text)]


# --- Nutrition maths ---------------------------------------------------------------------------
def test_bmr_uses_the_mifflin_st_jeor_equation_for_each_sex_option():
    assert mifflin_st_jeor_bmr(60, 165, 28, Sex.FEMALE) == pytest.approx(1330.25)
    assert mifflin_st_jeor_bmr(80, 180, 30, Sex.MALE) == pytest.approx(1780.0)
    assert mifflin_st_jeor_bmr(80, 180, 30, Sex.UNSPECIFIED) == pytest.approx(1697.0)


def test_targets_for_the_reference_profile():
    targets = compute_targets(make_request())

    assert targets.bmr == 1330
    assert targets.tdee == 2062
    assert targets.calories == 2060  # balanced goal keeps TDEE, rounded to 10 kcal
    assert (targets.protein_g, targets.carbs_g, targets.fat_g) == (103, 258, 69)  # 20/50/30 %
    assert targets.meal_calories == {"breakfast": 515, "lunch": 721, "snack": 206, "dinner": 618}
    assert targets.water_liters == 2.1  # 35 ml per kg


# --- TC-10: different goal ----------------------------------------------------------------------
def test_tc10_goal_changes_the_calorie_target_and_macro_split():
    weight = compute_targets(make_request(goal=Goal.WEIGHT_MANAGEMENT))
    balanced = compute_targets(make_request(goal=Goal.BALANCED))
    fitness = compute_targets(make_request(goal=Goal.FITNESS))

    assert weight.calories == 1750  # 2061.89 * 0.85
    assert fitness.calories == 2270  # 2061.89 * 1.10
    assert weight.calories < balanced.calories < fitness.calories
    assert fitness.macro_split["protein"] == 30 > balanced.macro_split["protein"] == 20


def test_calorie_target_never_drops_below_the_safety_floor():
    targets = compute_targets(
        make_request(age=90, height_cm=100, weight_kg=30,
                     activity_level=ActivityLevel.SEDENTARY, goal=Goal.WEIGHT_MANAGEMENT)
    )

    assert targets.calories == 1200


def test_very_active_people_get_a_higher_hydration_suggestion():
    targets = compute_targets(make_request(activity_level=ActivityLevel.VERY_ACTIVE))

    assert targets.water_liters == 2.6  # 2.1 L + 0.5 L for very active people


# --- Plan generation ----------------------------------------------------------------------------
def test_plan_has_all_four_meals_a_summary_hydration_tip_and_disclaimer():
    plan = generate()

    assert list(plan.meals) == list(MEAL_SLOTS)
    assert plan.source == "rule_based"
    assert plan.disclaimer == DISCLAIMER
    assert "2.1" in plan.hydration_tip
    assert plan.tips


def test_plan_totals_are_the_sum_of_the_meals():
    plan = generate()

    assert plan.totals.calories == sum(m.calories for m in plan.meals.values())
    assert plan.totals.protein_g == sum(m.protein_g for m in plan.meals.values())


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"goal": Goal.WEIGHT_MANAGEMENT, "activity_level": ActivityLevel.SEDENTARY},
        {"goal": Goal.FITNESS, "sex": Sex.MALE, "weight_kg": 85, "height_cm": 182,
         "activity_level": ActivityLevel.VERY_ACTIVE,
         "dietary_preference": DietaryPreference.NON_VEGETARIAN},
        {"dietary_preference": DietaryPreference.VEGAN, "allergies": frozenset({Allergen.SOY})},
    ],
)
def test_plan_calories_land_within_15_percent_of_the_target(overrides, seed):
    plan = generate(seed=seed, **overrides)

    target = plan.targets.calories
    assert abs(plan.totals.calories - target) / target <= 0.15


@pytest.mark.parametrize("seed", range(10))
def test_tc08_vegetarian_plan_contains_no_meat_fish_or_eggs(seed):
    plan = generate(seed=seed, dietary_preference=DietaryPreference.VEGETARIAN)

    for meal in plan.meals.values():
        assert meal.diet in ("vegetarian", "vegan")
        assert not contains_word(meal_text(meal), ["chicken", "fish", "egg", "prawn", "tuna",
                                                   "salmon", "mutton"])


@pytest.mark.parametrize("seed", range(10))
def test_tc09_vegan_plan_contains_no_animal_products(seed):
    plan = generate(seed=seed, dietary_preference=DietaryPreference.VEGAN)

    for meal in plan.meals.values():
        assert meal.diet == "vegan"
        assert not contains_word(meal_text(meal), ["chicken", "fish", "egg", "paneer", "yogurt",
                                                   "cheese", "ghee", "honey", "curd"])


@pytest.mark.parametrize("seed", range(10))
def test_allergens_are_never_included(seed):
    allergies = frozenset({Allergen.PEANUTS, Allergen.DAIRY, Allergen.GLUTEN})

    plan = generate(seed=seed, dietary_preference=DietaryPreference.NON_VEGETARIAN,
                    allergies=allergies)

    for meal in plan.meals.values():
        assert not set(meal.allergens) & allergies


def test_cuisine_preference_is_used_when_enough_dishes_match():
    plan = generate(cuisine=Cuisine.INDIAN)

    assert {meal.cuisine for meal in plan.meals.values()} == {"indian"}


def test_the_same_seed_reproduces_a_plan_and_different_seeds_add_variety():
    assert generate(seed=1).model_dump() == generate(seed=1).model_dump()

    names = {tuple(m.name for m in generate(seed=s).meals.values()) for s in range(10)}
    assert len(names) > 1


def test_no_dish_is_repeated_within_one_plan():
    for seed in range(10):
        plan = generate(seed=seed)
        ids = [meal.food_id for meal in plan.meals.values()]
        assert len(ids) == len(set(ids))


def test_portions_are_scaled_in_quarter_serving_steps():
    plan = generate(goal=Goal.FITNESS, sex=Sex.MALE, weight_kg=95, height_cm=188,
                    activity_level=ActivityLevel.EXTRA_ACTIVE)

    for meal in plan.meals.values():
        assert 0.5 <= meal.servings <= 2.0
        assert (meal.servings * 4) == int(meal.servings * 4)


def test_impossible_restrictions_raise_a_clear_error():
    breakfast_only = [
        FoodItem(id="toast", name="Toast", description="Plain toast.", meal_types=["breakfast"],
                 diet="vegan", cuisine="international", allergens=["gluten"], portion="2 slices",
                 ingredients=["bread"], calories=160, protein_g=6, carbs_g=30, fat_g=2, fiber_g=3),
    ]
    engine = RuleBasedDietEngine(foods=breakfast_only)

    with pytest.raises(NoSuitableMealsError) as error:
        engine.generate(make_request())

    assert error.value.slot == "lunch"  # breakfast can be served; nothing fits lunch


# --- Food dataset quality -----------------------------------------------------------------------
def test_every_dish_declares_calories_consistent_with_its_macros():
    for food in load_foods():
        from_macros = 4 * food.protein_g + 4 * food.carbs_g + 9 * food.fat_g
        assert abs(from_macros - food.calories) / food.calories <= 0.12, food.id


def test_every_diet_has_at_least_three_options_for_every_meal():
    engine = RuleBasedDietEngine()
    for diet in DietaryPreference:
        for slot in MEAL_SLOTS:
            assert len(engine.candidates(slot, make_request(dietary_preference=diet))) >= 3, \
                (diet, slot)


def test_strict_vegan_with_common_allergies_still_has_options_for_every_meal():
    engine = RuleBasedDietEngine()
    request = make_request(
        dietary_preference=DietaryPreference.VEGAN,
        allergies=frozenset({Allergen.GLUTEN, Allergen.SOY, Allergen.PEANUTS,
                             Allergen.TREE_NUTS, Allergen.SESAME}),
    )
    for slot in MEAL_SLOTS:
        assert len(engine.candidates(slot, request)) >= 2, slot
