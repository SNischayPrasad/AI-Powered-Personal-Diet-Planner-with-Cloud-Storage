"""Diet plan REST API — TC-07, TC-08/09/10 at API level, TC-13 (save) and TC-14 (retrieve)."""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from ai_engine.diet_engine import FoodItem, RuleBasedDietEngine
from backend.app import create_app
from tests.helpers import auth_headers, complete_profile, make_settings, register

MEALS = ("breakfast", "lunch", "snack", "dinner")


@pytest.fixture
def token(client) -> str:
    token = register(client)["access_token"]
    complete_profile(client, token)  # DEMO_PROFILE: vegetarian, balanced, 2,060 kcal target
    return token


def generate(client, token, **payload):
    return client.post("/api/generate-plan", json=payload, headers=auth_headers(token))


# --- TC-07: diet plan generation --------------------------------------------------------------
def test_tc07_generate_plan_returns_four_meals_nutrition_summary_and_disclaimer(client, token):
    response = generate(client, token)

    assert response.status_code == 201
    plan = response.json()
    uuid.UUID(plan["id"])
    for slot in MEALS:
        assert plan[slot]["name"]
        assert plan[slot]["calories"] > 0
    summary = plan["nutrition_summary"]
    assert summary["targets"]["calories"] == 2060  # hand-computed for DEMO_PROFILE
    assert summary["totals"]["calories"] == sum(plan[slot]["calories"] for slot in MEALS)
    assert "L of fluids" in plan["hydration_tip"]
    assert "not medical" in plan["disclaimer"]
    assert plan["source"] == "rule_based"


def test_generating_requires_a_complete_profile(client):
    token = register(client)["access_token"]

    response = generate(client, token)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "profile_incomplete"


def test_generating_requires_authentication(client):
    assert client.post("/api/generate-plan", json={}).status_code == 401


# --- TC-08 / TC-09 / TC-10 through the API -------------------------------------------------------
def test_tc08_vegetarian_profile_gets_only_vegetarian_dishes(client, token):
    plan = generate(client, token).json()

    assert {plan[slot]["diet"] for slot in MEALS} <= {"vegetarian", "vegan"}


def test_tc09_vegan_override_applies_to_this_plan_without_changing_the_profile(client, token):
    plan = generate(client, token, dietary_preference="vegan").json()
    profile = client.get("/api/profile", headers=auth_headers(token)).json()

    assert plan["dietary_preference"] == "vegan"
    assert {plan[slot]["diet"] for slot in MEALS} == {"vegan"}
    assert profile["dietary_preference"] == "vegetarian"


def test_tc10_weight_management_goal_lowers_the_calorie_target(client, token):
    balanced = generate(client, token).json()
    weight = generate(client, token, goal="weight_management").json()

    assert balanced["calorie_target"] == 2060
    assert weight["calorie_target"] == 1750
    assert weight["goal"] == "weight_management"


def test_allergy_override_excludes_those_allergens(client, token):
    plan = generate(client, token, allergies=["dairy", "gluten"]).json()

    for slot in MEALS:
        assert not {"dairy", "gluten"} & set(plan[slot]["allergens"])


def test_unknown_override_values_are_rejected(client, token):
    assert generate(client, token, goal="extreme_cut").status_code == 422


# --- TC-13: save diet plan -----------------------------------------------------------------------
def test_tc13_generated_plans_are_saved_to_the_database_newest_first(client, token):
    first = generate(client, token).json()
    second = generate(client, token, goal="fitness").json()

    listing = client.get("/api/plans", headers=auth_headers(token)).json()

    assert listing["total"] == 2
    assert [item["id"] for item in listing["items"]] == [second["id"], first["id"]]
    assert listing["items"][0]["total_calories"] == \
        second["nutrition_summary"]["totals"]["calories"]


def test_plan_listing_supports_pagination(client, token):
    for _ in range(3):
        generate(client, token)

    page = client.get("/api/plans?limit=2&offset=2", headers=auth_headers(token)).json()

    assert page["total"] == 3
    assert len(page["items"]) == 1


# --- TC-14: retrieve plan ------------------------------------------------------------------------
def test_tc14_a_saved_plan_can_be_retrieved_by_id(client, token):
    created = generate(client, token).json()

    fetched = client.get(f"/api/plans/{created['id']}", headers=auth_headers(token))

    assert fetched.status_code == 200
    assert fetched.json() == created


@pytest.mark.parametrize("plan_id", [str(uuid.uuid4()), "not-a-uuid", "../../etc/passwd"])
def test_missing_or_malformed_plan_ids_return_404(client, token, plan_id):
    assert client.get(f"/api/plans/{plan_id}", headers=auth_headers(token)).status_code == 404


def test_deleting_a_plan_removes_it(client, token):
    plan_id = generate(client, token).json()["id"]

    deleted = client.delete(f"/api/plans/{plan_id}", headers=auth_headers(token))

    assert deleted.status_code == 204
    assert client.get(f"/api/plans/{plan_id}", headers=auth_headers(token)).status_code == 404
    assert client.get("/api/plans", headers=auth_headers(token)).json()["total"] == 0


# --- Export / download ---------------------------------------------------------------------------
def test_plan_can_be_exported_as_json(client, token):
    plan = generate(client, token).json()

    response = client.get(f"/api/plans/{plan['id']}/export?format=json",
                          headers=auth_headers(token))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers["content-disposition"]
    assert json.loads(response.content)["id"] == plan["id"]


def test_plan_can_be_exported_as_a_readable_text_report(client, token):
    plan = generate(client, token).json()

    response = client.get(f"/api/plans/{plan['id']}/export?format=txt",
                          headers=auth_headers(token))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert plan["breakfast"]["name"] in response.text
    assert "DISCLAIMER" in response.text


def test_unsupported_export_format_is_rejected(client, token):
    plan_id = generate(client, token).json()["id"]

    response = client.get(f"/api/plans/{plan_id}/export?format=exe", headers=auth_headers(token))

    assert response.status_code == 422


# --- Abuse protection and edge cases -------------------------------------------------------------
def test_plan_generation_is_rate_limited_per_user(tmp_path):
    app = create_app(make_settings(tmp_path, rate_limit_generate_per_minute=2))
    with TestClient(app) as client:
        token = register(client)["access_token"]
        complete_profile(client, token)
        statuses = [generate(client, token).status_code for _ in range(3)]

    assert statuses == [201, 201, 429]


def test_restrictions_with_no_matching_dishes_return_a_helpful_422(client, token, app):
    app.state.diet_engine = RuleBasedDietEngine(foods=[
        FoodItem(id="only-breakfast", name="Toast", description="Toast.", meal_types=["breakfast"],
                 diet="vegan", cuisine="international", allergens=[], portion="2 slices",
                 ingredients=["bread"], calories=160, protein_g=6, carbs_g=30, fat_g=2,
                 fiber_g=3),
    ])

    response = generate(client, token)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_suitable_meals"
