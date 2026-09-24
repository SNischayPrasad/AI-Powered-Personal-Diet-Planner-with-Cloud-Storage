"""AI planner with validation and automatic fallback — TC-11 (AI API failure) and
TC-12 (rule-based fallback)."""

import json

import pytest
from fastapi.testclient import TestClient

from ai_engine.diet_engine import FoodItem, RuleBasedDietEngine
from ai_engine.llm_providers import AIProviderError
from ai_engine.options import Allergen, DietaryPreference
from ai_engine.planner import DietPlanner
from backend.app import create_app
from tests.ai_fixtures import ScriptedProvider, ai_plan, as_json, reference_request
from tests.helpers import auth_headers, complete_profile, make_settings, register

SLOTS = ("breakfast", "lunch", "snack", "dinner")


def plan_with(reply, *, request=None, use_ai=True):
    provider = ScriptedProvider(reply)
    planner = DietPlanner(provider, ai_requested=True)
    return planner.generate(request or reference_request(), use_ai=use_ai), provider


# --- AI path ----------------------------------------------------------------------------------
def test_a_valid_ai_answer_becomes_the_plan_and_is_labelled_as_ai():
    plan, _ = plan_with(as_json(ai_plan()))

    assert plan.source == "ai"
    assert plan.ai_provider == "scripted"
    assert plan.ai_model == "scripted-model-1"
    assert plan.fallback_reason is None
    assert plan.meals["lunch"].name == "Rajma Rice Bowl"
    assert plan.totals.calories == 500 + 720 + 210 + 630  # recomputed, never trusted


def test_ai_answers_wrapped_in_markdown_code_fences_are_accepted():
    plan, _ = plan_with("```json\n" + as_json(ai_plan()) + "\n```")

    assert plan.source == "ai"


def test_the_prompt_contains_preferences_and_targets_but_no_personal_details():
    _, provider = plan_with(as_json(ai_plan()), request=reference_request(
        allergies=frozenset({Allergen.PEANUTS})))

    prompt = provider.calls[0]["user"]
    payload = json.loads(prompt[prompt.index("{"):])
    assert payload["dietary_preference"] == "vegetarian"
    assert payload["allergies_to_exclude"] == ["peanuts"]
    assert payload["daily_calorie_target"] == 2060
    assert payload["meal_calorie_budgets"]["lunch"] == 721
    assert not {"age", "sex", "height_cm", "weight_kg", "name", "email"} & set(payload)


def test_the_provider_is_given_a_strict_json_schema():
    _, provider = plan_with(as_json(ai_plan()))

    schema = provider.calls[0]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {*SLOTS, "tips"}


# --- TC-11: AI API failure → fallback ------------------------------------------------------------
@pytest.mark.parametrize("reason", ["timeout", "rate_limited", "network_error",
                                    "authentication_failed", "refused", "api_error_529"])
def test_tc11_ai_provider_failures_fall_back_to_the_rule_based_engine(reason):
    plan, _ = plan_with(AIProviderError(reason))

    assert plan.source == "rule_based"
    assert plan.fallback_reason == reason
    assert all(plan.meals[slot].name for slot in SLOTS)


# --- TC-12: rule-based fallback / configuration --------------------------------------------------
def test_tc12_ai_requested_but_not_configured_uses_the_rule_based_engine():
    plan = DietPlanner(None, ai_requested=True).generate(reference_request())

    assert plan.source == "rule_based"
    assert plan.fallback_reason == "ai_not_configured"


def test_rule_based_engine_is_the_primary_engine_when_ai_is_not_enabled():
    plan = DietPlanner(None, ai_requested=False).generate(reference_request())

    assert plan.source == "rule_based"
    assert plan.fallback_reason is None


def test_users_can_switch_the_ai_off_for_one_plan():
    plan, provider = plan_with(as_json(ai_plan()), use_ai=False)

    assert plan.source == "rule_based"
    assert plan.fallback_reason == "ai_disabled"
    assert provider.calls == []


# --- Response validation (guardrails) ------------------------------------------------------------
@pytest.mark.parametrize(
    ("reply", "request_overrides", "reason"),
    [
        ("Sure! Here is a healthy plan for you.", {}, "invalid_json"),
        (json.dumps({"breakfast": {"name": "Toast"}}), {}, "invalid_schema"),
        (as_json(ai_plan(dinner={"name": "Butter Chicken with Naan",
                                 "ingredients": ["chicken", "butter", "naan"]})), {},
         "diet_violation"),
        (as_json(ai_plan(breakfast={"ingredients": ["eggs", "onion", "tomato"]})), {},
         "diet_violation"),
        (as_json(ai_plan()), {"dietary_preference": DietaryPreference.VEGAN}, "diet_violation"),
        (as_json(ai_plan(snack={"name": "Apple with Peanut Butter",
                                "ingredients": ["apple", "peanut butter"]})),
         {"allergies": frozenset({Allergen.PEANUTS})}, "allergen_violation"),
        (as_json(ai_plan(lunch={"ingredients": ["kidney beans", "rice", "cashews"]})),
         {"allergies": frozenset({Allergen.TREE_NUTS})}, "allergen_violation"),
        (as_json(ai_plan(dinner={"calories": 100, "protein_g": 5, "carbs_g": 15, "fat_g": 3})),
         {}, "calorie_mismatch"),
        (as_json(ai_plan(lunch={"protein_g": 1, "carbs_g": 1, "fat_g": 1})), {},
         "inconsistent_nutrition"),
    ],
)
def test_unsafe_or_malformed_ai_answers_are_rejected_and_replaced(reply, request_overrides,
                                                                  reason):
    plan, _ = plan_with(reply, request=reference_request(**request_overrides))

    assert plan.source == "rule_based"
    assert plan.fallback_reason == reason


def test_plant_based_alternatives_are_not_mistaken_for_animal_products():
    vegan_reply = ai_plan(
        breakfast={"name": "Overnight Oats with Oat Milk",
                   "description": "Oats soaked overnight in oat milk.",
                   "ingredients": ["rolled oats", "oat milk", "chia seeds", "banana"]},
        snack={"name": "Apple with Peanut Butter", "description": "A crisp apple, sliced.",
               "ingredients": ["apple", "peanut butter"]},
        lunch={"name": "Baingan Bharta with Brown Rice",
               "description": "Smoky mashed eggplant with rice.",
               "ingredients": ["eggplant", "onion", "tomato", "brown rice"]},
        dinner={"name": "Tofu Curry with Coconut Yogurt",
                "description": "Bean curd simmered in a coconut milk gravy.",
                "portion": "1 bowl curry + 1 cup rice",
                "ingredients": ["tofu", "coconut milk", "coconut yogurt", "rice"]},
    )

    plan, _ = plan_with(as_json(vegan_reply),
                        request=reference_request(dietary_preference=DietaryPreference.VEGAN))

    assert plan.source == "ai"


def test_gluten_free_grains_are_allowed_for_a_gluten_allergy():
    reply = ai_plan(
        lunch={"name": "Rice Noodles with Tamari Vegetables",
               "description": "Stir-fried rice noodles with crunchy vegetables.",
               "portion": "1 large bowl",
               "ingredients": ["rice noodles", "tamari", "broccoli", "carrot"]},
        dinner={"name": "Paneer Bhurji with Jowar Roti",
                "description": "Crumbled paneer with a sorghum flatbread.",
                "portion": "1 bowl bhurji + 2 jowar rotis",
                "ingredients": ["paneer", "onion", "tomato", "jowar flour"]},
    )

    plan, _ = plan_with(as_json(reply),
                        request=reference_request(allergies=frozenset({Allergen.GLUTEN})))

    assert plan.source == "ai"


# --- Through the REST API ------------------------------------------------------------------------
def _ready_user(client) -> str:
    token = register(client)["access_token"]
    complete_profile(client, token)
    return token


def test_api_reports_the_fallback_reason_and_counts_it_in_metrics(tmp_path):
    # AI requested, but the OpenAI-compatible endpoint was never configured.
    app = create_app(make_settings(tmp_path, ai_provider="openai_compatible"))
    with TestClient(app) as client:
        token = _ready_user(client)
        plan = client.post("/api/generate-plan", json={}, headers=auth_headers(token)).json()
        status = client.get("/api/system/status").json()
        metrics = client.get("/api/metrics").text

    assert plan["source"] == "rule_based"
    assert plan["fallback_reason"] == "ai_not_configured"
    assert status["ai_provider"] == "openai_compatible"
    assert status["ai_available"] is False
    assert 'ai_fallbacks_total{reason="ai_not_configured"} 1' in metrics


def test_api_saves_ai_generated_plans_with_their_provenance(client, app):
    app.state.planner = DietPlanner(ScriptedProvider(as_json(ai_plan())), ai_requested=True)
    token = _ready_user(client)

    created = client.post("/api/generate-plan", json={}, headers=auth_headers(token)).json()
    fetched = client.get(f"/api/plans/{created['id']}", headers=auth_headers(token)).json()

    assert fetched["source"] == "ai"
    assert fetched["ai_model"] == "scripted-model-1"
    assert fetched["lunch"]["name"] == "Rajma Rice Bowl"


def test_api_lets_the_user_turn_the_ai_off(client, app):
    provider = ScriptedProvider(as_json(ai_plan()))
    app.state.planner = DietPlanner(provider, ai_requested=True)
    token = _ready_user(client)

    plan = client.post("/api/generate-plan", json={"use_ai": False},
                       headers=auth_headers(token)).json()

    assert plan["source"] == "rule_based"
    assert plan["fallback_reason"] == "ai_disabled"
    assert provider.calls == []


def test_no_matching_dishes_is_still_reported_when_the_ai_fails(client, app):
    toast_only = RuleBasedDietEngine(foods=[
        FoodItem(id="toast", name="Toast", description="Toast.", meal_types=["breakfast"],
                 diet="vegan", cuisine="international", allergens=[], portion="2 slices",
                 ingredients=["bread"], calories=160, protein_g=6, carbs_g=30, fat_g=2,
                 fiber_g=3),
    ])
    app.state.planner = DietPlanner(ScriptedProvider(AIProviderError("timeout")),
                                    ai_requested=True, rule_engine=toast_only)
    token = _ready_user(client)

    response = client.post("/api/generate-plan", json={}, headers=auth_headers(token))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_suitable_meals"
