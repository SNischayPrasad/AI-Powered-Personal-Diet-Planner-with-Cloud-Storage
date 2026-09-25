"""Capture the README screenshots from a running local stack.

Prerequisites (one-time):
    pip install playwright          # uses your installed Microsoft Edge; no browser download

Start the API (port 8000) and the frontend (port 5173), then:
    python scripts/capture_screenshots.py

A fresh synthetic user ("Meera Demo", random email and password) is created through the REST
API, given a profile, three plans, two uploaded meal illustrations and a plan saved to cloud
storage, and then every page is photographed into screenshots/.
"""

import argparse
import secrets
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_IMAGES = ROOT / "sample_data" / "images"
DESKTOP = {"width": 1366, "height": 860}
MOBILE = {"width": 390, "height": 844}

PROFILE = {
    "name": "Meera Demo",
    "age": 26,
    "sex": "female",
    "height_cm": 160,
    "weight_kg": 55,
    "activity_level": "lightly_active",
    "dietary_preference": "vegetarian",
    "goal": "balanced",
    "allergies": ["peanuts"],
    "cuisine_preference": "any",
}


def seed_demo_user(app_url: str) -> str:
    """Create the demo account and its data through the public API; return its token."""
    api = httpx.Client(base_url=app_url, timeout=60)
    email = f"meera.demo.{secrets.token_hex(3)}@example.com"
    password = f"Demo-{secrets.token_urlsafe(9)}7"
    token = api.post("/api/register", json={"name": "Meera Demo", "email": email,
                                            "password": password}).raise_for_status()
    headers = {"Authorization": f"Bearer {token.json()['access_token']}"}
    api.put("/api/profile", json=PROFILE, headers=headers).raise_for_status()

    api.post("/api/generate-plan", json={"goal": "fitness", "dietary_preference": "vegan"},
             headers=headers).raise_for_status()
    older = api.post("/api/generate-plan", json={"goal": "weight_management"},
                     headers=headers).raise_for_status().json()
    for image in ("breakfast-poha-bowl.png", "lunch-thali.png"):
        api.post("/api/upload", files={"file": (image, (SAMPLE_IMAGES / image).read_bytes(),
                                                "image/png")},
                 headers=headers).raise_for_status()
    api.post(f"/api/plans/{older['id']}/save-to-cloud?format=txt",
             headers=headers).raise_for_status()
    api.post("/api/generate-plan", json={}, headers=headers).raise_for_status()  # latest plan
    print(f"Seeded demo user {email}")
    return headers["Authorization"].removeprefix("Bearer ")


def settle(page: Page, selector: str | None = None) -> None:
    page.wait_for_load_state("networkidle")
    if selector:
        page.locator(selector).first.wait_for(state="visible")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(400)


def shoot(page: Page, out: Path, name: str, *, full_page: bool = False) -> None:
    path = out / name
    page.screenshot(path=str(path), full_page=full_page)
    print(f"  {name}")


def capture(app_url: str, api_url: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    token = seed_demo_user(app_url)
    set_token = f"localStorage.setItem('dietplanner.token', '{token}')"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge")

        public = browser.new_context(viewport=DESKTOP, reduced_motion="reduce")
        page = public.new_page()
        page.goto(app_url)
        settle(page, ".thali")
        shoot(page, out, "01-landing.png")
        page.locator("#cloud-heading").scroll_into_view_if_needed()
        settle(page, ".status-pill")
        page.locator("section[aria-labelledby='cloud-heading']").screenshot(
            path=str(out / "12-architecture.png"))
        print("  12-architecture.png")
        page.goto(f"{app_url}/register")
        settle(page, "form")
        shoot(page, out, "02-register.png")
        page.goto(f"{api_url}/api/docs")
        settle(page, ".swagger-ui .opblock")
        shoot(page, out, "11-api-docs.png")
        public.close()

        desktop = browser.new_context(viewport=DESKTOP, reduced_motion="reduce")
        desktop.add_init_script(set_token)
        page = desktop.new_page()
        page.goto(f"{app_url}/dashboard")
        settle(page, ".latest .thali")
        shoot(page, out, "03-dashboard.png", full_page=True)
        page.goto(f"{app_url}/profile")
        settle(page, ".profile__form")
        shoot(page, out, "04-profile.png", full_page=True)
        page.goto(f"{app_url}/generate")
        settle(page, ".generate__grid")
        shoot(page, out, "05-generate-plan.png", full_page=True)
        page.goto(f"{app_url}/plans")
        settle(page, ".table")
        shoot(page, out, "08-saved-plans.png")
        page.locator(".table a.link").first.click()
        settle(page, ".plan__overview .thali")
        shoot(page, out, "06-plan-result.png")
        page.locator("#meals-heading").evaluate("el => window.scrollTo(0, el.offsetTop - 80)")
        settle(page)
        shoot(page, out, "07-plan-meals.png")
        page.goto(f"{app_url}/files")
        settle(page, ".file-tile__preview img")
        shoot(page, out, "09-cloud-files.png", full_page=True)
        desktop.close()

        mobile = browser.new_context(viewport=MOBILE, device_scale_factor=2, is_mobile=True,
                                     reduced_motion="reduce")
        mobile.add_init_script(set_token)
        page = mobile.new_page()
        page.goto(f"{app_url}/dashboard")
        settle(page, ".latest .thali")
        shoot(page, out, "10-mobile-dashboard.png")
        mobile.close()

        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture README screenshots.")
    parser.add_argument("--app-url", default="http://localhost:5173")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--out", default=str(ROOT / "screenshots"))
    args = parser.parse_args()
    capture(args.app_url.rstrip("/"), args.api_url.rstrip("/"), Path(args.out))
