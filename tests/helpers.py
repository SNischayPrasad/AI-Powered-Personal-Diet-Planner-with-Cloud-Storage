"""Reusable helpers for the test-suite (builders for settings, users and requests)."""

import os
import struct
import zlib
from uuid import uuid4

from backend.config import Settings

# Set TEST_DATABASE_URL (e.g. postgresql://…) to run the whole suite against PostgreSQL,
# as the CI pipeline does. Otherwise every test gets its own temporary SQLite file.
EXTERNAL_TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

TEST_JWT_SECRET = "test-only-signing-key-that-is-long-enough-for-hs256-0123456789"
DEFAULT_PASSWORD = "Str0ngPassw0rd!"


def make_settings(tmp_path, **overrides) -> Settings:
    """Build isolated settings. Every value is passed explicitly so a developer's own
    environment variables or .env file can never leak into the test run."""
    values = {
        "environment": "test",
        "log_level": "WARNING",
        "database_url": EXTERNAL_TEST_DATABASE_URL
        or f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        "local_storage_dir": str(tmp_path / "object_storage"),
        "storage_provider": "local",
        "jwt_secret_key": TEST_JWT_SECRET,
        "bcrypt_rounds": 4,  # fast hashing for tests; production uses 12
        "ai_provider": "rule_based",
        "rate_limit_auth_per_minute": 1000,
        "rate_limit_generate_per_minute": 1000,
        "cors_origins": "http://localhost:5173",
        "metrics_enabled": True,
        "frontend_dist_dir": None,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def register(client, *, email: str | None = None, name: str = "Demo User",
             password: str = DEFAULT_PASSWORD) -> dict:
    """Register a synthetic demo user and return the API response body (token + user)."""
    email = email or f"user-{uuid4().hex[:10]}@example.com"
    response = client.post(
        "/api/register", json={"name": name, "email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# A synthetic demo profile — not a real person.
DEMO_PROFILE = {
    "age": 28,
    "sex": "female",
    "height_cm": 165,
    "weight_kg": 60,
    "activity_level": "moderately_active",
    "dietary_preference": "vegetarian",
    "goal": "balanced",
    "allergies": [],
    "cuisine_preference": "any",
}


def png_bytes(width: int = 2, height: int = 2) -> bytes:
    """A real, valid PNG image built with the standard library (no image files needed)."""
    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return (struct.pack(">I", len(payload)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    rows = b"".join(b"\x00" + b"\x2e\xa0\x5b" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 64 + b"\xff\xd9"
PDF_BYTES = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << >>\n%%EOF\n"


def upload(client, token: str, filename: str, data: bytes,
           content_type: str = "application/octet-stream"):
    return client.post(
        "/api/upload",
        files={"file": (filename, data, content_type)},
        headers=auth_headers(token),
    )


def complete_profile(client, token: str, **overrides) -> dict:
    """Save a full profile for the user owning ``token`` and return the API response."""
    payload = {**DEMO_PROFILE, **overrides}
    response = client.put("/api/profile", json=payload, headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()
