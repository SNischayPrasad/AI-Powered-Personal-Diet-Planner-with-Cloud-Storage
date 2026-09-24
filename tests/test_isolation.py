"""TC-18: one user can never read, change or delete another user's data.

Alice owns a plan and a file. Bob is a different, fully authenticated user. Every endpoint
that takes a resource ID must behave for Bob exactly as if Alice's resource did not exist.
"""

import pytest

from tests.helpers import auth_headers, complete_profile, png_bytes, register, upload


@pytest.fixture
def world(client) -> dict:
    alice = register(client, email="alice@example.com", name="Alice Demo")["access_token"]
    bob = register(client, email="bob@example.com", name="Bob Demo")["access_token"]
    complete_profile(client, alice)
    complete_profile(client, bob)
    plan_id = client.post("/api/generate-plan", json={}, headers=auth_headers(alice)).json()["id"]
    file_id = upload(client, alice, "alice-lunch.png", png_bytes()).json()["id"]
    return {"alice": alice, "bob": bob, "plan_id": plan_id, "file_id": file_id}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/plans/{plan_id}"),
        ("get", "/api/plans/{plan_id}/export?format=json"),
        ("get", "/api/plans/{plan_id}/export?format=txt"),
        ("post", "/api/plans/{plan_id}/save-to-cloud?format=txt"),
        ("delete", "/api/plans/{plan_id}"),
        ("get", "/api/files/{file_id}/download"),
        ("delete", "/api/files/{file_id}"),
    ],
)
def test_tc18_another_users_resources_look_like_they_do_not_exist(client, world, method, path):
    response = getattr(client, method)(path.format(**world), headers=auth_headers(world["bob"]))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_tc18_lists_only_contain_the_callers_own_data(client, world):
    bob = auth_headers(world["bob"])

    assert client.get("/api/plans", headers=bob).json()["total"] == 0
    assert client.get("/api/files", headers=bob).json()["total"] == 0


def test_tc18_rejected_cross_user_deletes_leave_the_owners_data_intact(client, world):
    alice, bob = auth_headers(world["alice"]), auth_headers(world["bob"])

    client.delete(f"/api/plans/{world['plan_id']}", headers=bob)
    client.delete(f"/api/files/{world['file_id']}", headers=bob)

    assert client.get(f"/api/plans/{world['plan_id']}", headers=alice).status_code == 200
    assert client.get(f"/api/files/{world['file_id']}/download", headers=alice).content \
        == png_bytes()


def test_tc18_saving_someone_elses_plan_creates_nothing(client, world):
    bob = auth_headers(world["bob"])

    client.post(f"/api/plans/{world['plan_id']}/save-to-cloud?format=json", headers=bob)

    assert client.get("/api/files", headers=bob).json()["total"] == 0


def test_tc18_the_profile_endpoint_only_ever_returns_the_callers_profile(client, world):
    profile = client.get("/api/profile", headers=auth_headers(world["bob"])).json()

    assert profile["email"] == "bob@example.com"
