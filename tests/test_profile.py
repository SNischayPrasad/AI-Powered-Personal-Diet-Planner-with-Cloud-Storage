"""User profile management — TC-05 (unauthorized access) and TC-06 (profile creation)."""

import pytest

from tests.helpers import DEMO_PROFILE, auth_headers, complete_profile, register


# --- TC-05: unauthorized dashboard access -----------------------------------------------------
@pytest.mark.parametrize("method", ["get", "put"])
def test_tc05_profile_requires_authentication(client, method):
    response = getattr(client, method)("/api/profile", **({"json": DEMO_PROFILE}
                                                            if method == "put" else {}))

    assert response.status_code == 401


# --- TC-06: profile creation ---------------------------------------------------------------------
def test_new_account_starts_with_an_incomplete_profile(client):
    token = register(client, name="Ravi Demo")["access_token"]

    profile = client.get("/api/profile", headers=auth_headers(token)).json()

    assert profile["name"] == "Ravi Demo"
    assert profile["profile_complete"] is False
    assert profile["age"] is None
    assert profile["allergies"] == []


def test_tc06_profile_is_saved_and_returned(client):
    token = register(client)["access_token"]

    saved = complete_profile(
        client, token, age=31, weight_kg=72.5, goal="fitness", allergies=["peanuts", "dairy"]
    )
    fetched = client.get("/api/profile", headers=auth_headers(token)).json()

    assert saved == fetched
    assert fetched["profile_complete"] is True
    assert fetched["age"] == 31
    assert fetched["weight_kg"] == 72.5
    assert fetched["goal"] == "fitness"
    assert fetched["dietary_preference"] == "vegetarian"
    assert fetched["allergies"] == ["peanuts", "dairy"]


def test_login_response_includes_the_saved_profile(client):
    body = register(client, email="profile-login@example.com")
    complete_profile(client, body["access_token"], goal="weight_management")

    login = client.post(
        "/api/login",
        json={"email": "profile-login@example.com", "password": "Str0ngPassw0rd!"},
    ).json()

    assert login["user"]["goal"] == "weight_management"
    assert login["user"]["profile_complete"] is True


def test_profile_update_can_rename_the_user(client):
    token = register(client, name="Old Name")["access_token"]

    updated = complete_profile(client, token, name="  New Name  ")

    assert updated["name"] == "New Name"


def test_profile_update_cannot_change_the_email(client):
    body = register(client, email="fixed@example.com")

    updated = complete_profile(client, body["access_token"], email="attacker@example.com")

    assert updated["email"] == "fixed@example.com"


def test_duplicate_allergies_are_stored_once(client):
    token = register(client)["access_token"]

    updated = complete_profile(client, token, allergies=["gluten", "gluten", "soy"])

    assert updated["allergies"] == ["gluten", "soy"]


def test_sex_is_optional_and_defaults_to_unspecified(client):
    token = register(client)["access_token"]
    payload = {key: value for key, value in DEMO_PROFILE.items() if key != "sex"}

    response = client.put("/api/profile", json=payload, headers=auth_headers(token))

    assert response.json()["sex"] == "unspecified"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("age", 17),  # the calorie formulas used are for adults
        ("age", 91),
        ("height_cm", 99),
        ("height_cm", 251),
        ("weight_kg", 29),
        ("weight_kg", 301),
        ("activity_level", "couch_potato"),
        ("dietary_preference", "keto"),
        ("goal", "bulk_at_any_cost"),
        ("allergies", ["kryptonite"]),
        ("cuisine_preference", "martian"),
    ],
)
def test_out_of_range_or_unknown_profile_values_are_rejected(client, field, value):
    token = register(client)["access_token"]

    response = client.put(
        "/api/profile", json={**DEMO_PROFILE, field: value}, headers=auth_headers(token)
    )

    assert response.status_code == 422
    assert field in response.json()["error"]["message"]


def test_profile_update_requires_the_core_fields(client):
    token = register(client)["access_token"]

    response = client.put("/api/profile", json={"age": 30}, headers=auth_headers(token))

    assert response.status_code == 422
