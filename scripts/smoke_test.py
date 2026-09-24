"""End-to-end smoke test for a running deployment (local, Docker, Render, Vercel, AWS…).

    python scripts/smoke_test.py                                   # http://localhost:8000
    python scripts/smoke_test.py --base-url https://your-app.example.com

It walks the whole user journey through the public REST API with two throwaway synthetic
users (random emails): health checks, registration, login, profile, plan generation, export,
cloud storage, user isolation, logout and token revocation. Exit code 0 means every check
passed, so it can gate a deployment in CI/CD.
"""

import argparse
import secrets
import struct
import sys
import zlib

import httpx


def tiny_png() -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00\xa8\x5a\x27\xa8\x5a\x27" * 2)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels)
            + chunk(b"IEND", b""))


class Smoke:
    def __init__(self, base_url: str) -> None:
        self.http = httpx.Client(base_url=base_url.rstrip("/"), timeout=90)
        self.passed = 0
        self.failed = 0

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        if ok:
            self.passed += 1
            print(f"  PASS  {name}")
        else:
            self.failed += 1
            print(f"  FAIL  {name}  {detail}")
        return ok

    def user(self, label: str) -> tuple[str, str, str]:
        email = f"smoke-{label}-{secrets.token_hex(4)}@example.com"
        password = f"Smoke-{secrets.token_urlsafe(9)}1"
        response = self.http.post("/api/register",
                                  json={"name": f"Smoke {label}", "email": email,
                                        "password": password})
        self.check(f"register {label}", response.status_code == 201, response.text[:200])
        return email, password, response.json().get("access_token", "")


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


PROFILE = {"age": 30, "sex": "unspecified", "height_cm": 170, "weight_kg": 68,
           "activity_level": "lightly_active", "dietary_preference": "vegetarian",
           "goal": "balanced", "allergies": ["peanuts"], "cuisine_preference": "any"}


def run(base_url: str) -> int:
    s = Smoke(base_url)
    http = s.http
    print(f"Smoke test against {base_url}\n")

    print("Platform")
    health = http.get("/api/health")
    s.check("liveness /api/health", health.status_code == 200)
    s.check("security header present", health.headers.get("x-content-type-options") == "nosniff")
    ready = http.get("/api/health/ready")
    s.check("readiness /api/health/ready", ready.status_code == 200, ready.text[:200])
    status = http.get("/api/system/status").json()
    print(f"        providers: database={status.get('database_provider')} "
          f"storage={status.get('storage_provider')} ai={status.get('ai_provider')}")

    print("\nAuthentication")
    email, password, token = s.user("a")
    duplicate = http.post("/api/register", json={"name": "Dup", "email": email,
                                                 "password": password})
    s.check("duplicate email rejected (409)", duplicate.status_code == 409)
    wrong = http.post("/api/login", json={"email": email, "password": password + "x"})
    s.check("wrong password rejected (401)", wrong.status_code == 401)
    login = http.post("/api/login", json={"email": email, "password": password})
    s.check("login", login.status_code == 200)
    token = login.json().get("access_token", token)
    s.check("protected route without token (401)", http.get("/api/profile").status_code == 401)

    print("\nProfile and plans")
    profile = http.put("/api/profile", json=PROFILE, headers=auth(token))
    s.check("profile saved", profile.status_code == 200 and profile.json()["profile_complete"])
    plan = http.post("/api/generate-plan", json={}, headers=auth(token))
    s.check("plan generated (201)", plan.status_code == 201, plan.text[:200])
    plan = plan.json()
    fallback = f" (fallback: {plan['fallback_reason']})" if plan.get("fallback_reason") else ""
    print(f"        engine: {plan.get('source')}{fallback}")
    meals = [plan.get(slot) or {} for slot in ("breakfast", "lunch", "snack", "dinner")]
    s.check("four meals returned", all(meal.get("name") for meal in meals))
    s.check("peanut allergy respected",
            all("peanuts" not in meal.get("allergens", []) for meal in meals))
    vegan = http.post("/api/generate-plan", json={"dietary_preference": "vegan"},
                      headers=auth(token)).json()
    s.check("vegan override", all(vegan[slot]["diet"] == "vegan"
                                  for slot in ("breakfast", "lunch", "snack", "dinner")))
    listing = http.get("/api/plans", headers=auth(token)).json()
    s.check("plans saved in the database", listing.get("total", 0) >= 2)
    s.check("plan retrieved by id",
            http.get(f"/api/plans/{plan['id']}", headers=auth(token)).status_code == 200)
    report = http.get(f"/api/plans/{plan['id']}/export?format=txt", headers=auth(token))
    s.check("text export downloads", report.status_code == 200 and "DISCLAIMER" in report.text)

    print("\nCloud storage")
    saved = http.post(f"/api/plans/{plan['id']}/save-to-cloud?format=json", headers=auth(token))
    s.check("plan copy saved to object storage", saved.status_code == 201, saved.text[:200])
    image = tiny_png()
    uploaded = http.post("/api/upload", files={"file": ("smoke.png", image, "image/png")},
                         headers=auth(token))
    s.check("image uploaded", uploaded.status_code == 201, uploaded.text[:200])
    bad = http.post("/api/upload", files={"file": ("evil.exe", b"MZ\x90\x00", "image/png")},
                    headers=auth(token))
    s.check("disguised executable rejected (415)", bad.status_code == 415)
    file_id = uploaded.json().get("id", "")
    download = http.get(f"/api/files/{file_id}/download", headers=auth(token))
    s.check("image downloads byte-for-byte", download.content == image)

    print("\nUser isolation")
    _, _, other = s.user("b")
    s.check("other user cannot read the plan (404)",
            http.get(f"/api/plans/{plan['id']}", headers=auth(other)).status_code == 404)
    s.check("other user cannot download the file (404)",
            http.get(f"/api/files/{file_id}/download", headers=auth(other)).status_code == 404)
    s.check("other user's lists are empty",
            http.get("/api/plans", headers=auth(other)).json().get("total") == 0)

    print("\nClean-up and logout")
    s.check("file deleted",
            http.delete(f"/api/files/{file_id}", headers=auth(token)).status_code == 204)
    s.check("plan deleted",
            http.delete(f"/api/plans/{plan['id']}", headers=auth(token)).status_code == 204)
    s.check("logout", http.post("/api/logout", headers=auth(token)).status_code == 200)
    reuse = http.get("/api/profile", headers=auth(token))
    s.check("logged-out token rejected (401)", reuse.status_code == 401)

    print(f"\n{s.passed} passed, {s.failed} failed")
    return 0 if s.failed == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8000")
    sys.exit(run(parser.parse_args().base_url))
