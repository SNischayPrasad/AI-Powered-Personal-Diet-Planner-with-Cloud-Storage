"""scripts/seed_demo_data.py loads the synthetic demo users through the public API."""

import json

import pytest

from scripts.seed_demo_data import DEMO_USERS, demo_password, seed_user
from tests.helpers import auth_headers

PASSWORD = "Seed-Demo-2026"


@pytest.fixture
def demo_users():
    return json.loads(DEMO_USERS.read_text(encoding="utf-8"))["users"]


def test_demo_data_is_synthetic_and_contains_no_passwords(demo_users):
    raw = DEMO_USERS.read_text(encoding="utf-8").lower()

    assert "password" not in raw.replace("passwords are never stored", "")
    assert all(user["email"].endswith("@example.com") for user in demo_users)


def test_each_demo_user_gets_a_profile_a_plan_and_their_files(client, demo_users):
    for user in demo_users:
        seed_user(client, user, PASSWORD)

    asha = demo_users[0]
    token = client.post("/api/login", json={"email": asha["email"],
                                            "password": PASSWORD}).json()["access_token"]
    profile = client.get("/api/profile", headers=auth_headers(token)).json()
    files = client.get("/api/files", headers=auth_headers(token)).json()["items"]

    assert profile["dietary_preference"] == "vegetarian"
    assert profile["allergies"] == ["peanuts"]
    assert client.get("/api/plans", headers=auth_headers(token)).json()["total"] == 1
    assert sorted(f["category"] for f in files) == ["meal_image", "meal_image", "plan_export"]


def test_running_the_seed_twice_logs_in_instead_of_failing(client, demo_users):
    seed_user(client, demo_users[1], PASSWORD)
    seed_user(client, demo_users[1], PASSWORD)

    token = client.post("/api/login", json={"email": demo_users[1]["email"],
                                            "password": PASSWORD}).json()["access_token"]
    assert client.get("/api/plans", headers=auth_headers(token)).json()["total"] == 2


def test_password_comes_from_the_environment_or_is_random(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", PASSWORD)
    assert demo_password() == (PASSWORD, False)

    monkeypatch.delenv("DEMO_PASSWORD")
    first, generated = demo_password()
    assert generated and first != demo_password()[0]
