"""Load the synthetic demo users from sample_data/demo_users.json into a running deployment.

    python scripts/seed_demo_data.py                                  # http://localhost:8000
    python scripts/seed_demo_data.py --base-url https://your-app.example.com

Everything goes through the public REST API (register → profile → plan → uploads), so the
same script works locally, in Docker and in the cloud, and exercises the real code paths.

Passwords are never stored in the repository. Set DEMO_PASSWORD to choose one (at least 8
characters with a letter and a number); otherwise a random password is generated and printed
once. Users that already exist are logged in instead of re-created.
"""

import argparse
import json
import os
import secrets
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DEMO_USERS = ROOT / "sample_data" / "demo_users.json"
SAMPLE_IMAGES = ROOT / "sample_data" / "images"


def demo_password() -> tuple[str, bool]:
    """Return (password, generated?)."""
    chosen = os.environ.get("DEMO_PASSWORD", "").strip()
    if chosen:
        return chosen, False
    return f"Demo-{secrets.token_urlsafe(9)}7", True


def sign_in(api: httpx.Client, user: dict, password: str) -> str:
    """Register the user, or log in if the email is already registered; return a token."""
    response = api.post("/api/register", json={"name": user["name"], "email": user["email"],
                                              "password": password})
    if response.status_code == 409:
        response = api.post("/api/login", json={"email": user["email"], "password": password})
        if response.status_code == 401:
            sys.exit(f"{user['email']} already exists with a different password. "
                     "Set DEMO_PASSWORD to its password, or use a fresh database.")
    response.raise_for_status()
    return response.json()["access_token"]


def seed_user(api: httpx.Client, user: dict, password: str) -> dict:
    headers = {"Authorization": f"Bearer {sign_in(api, user, password)}"}
    api.put("/api/profile", json={"name": user["name"], **user["profile"]},
            headers=headers).raise_for_status()
    plan = api.post("/api/generate-plan", json={}, headers=headers).raise_for_status().json()
    for image in user.get("upload_images", []):
        api.post("/api/upload", headers=headers, files={
            "file": (image, (SAMPLE_IMAGES / image).read_bytes(), "image/png"),
        }).raise_for_status()
    if user.get("upload_images"):
        api.post(f"/api/plans/{plan['id']}/save-to-cloud?format=txt",
                 headers=headers).raise_for_status()
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic demo users.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    users = json.loads(DEMO_USERS.read_text(encoding="utf-8"))["users"]
    password, generated = demo_password()
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=90) as api:
        api.get("/api/health").raise_for_status()
        for user in users:
            plan = seed_user(api, user, password)
            print(f"  {user['email']:<26} plan: {plan['title']}")

    print(f"\nSeeded {len(users)} demo users at {args.base_url}")
    if generated:
        print(f"Password for all demo users (shown once): {password}")


if __name__ == "__main__":
    main()
