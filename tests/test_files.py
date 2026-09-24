"""Cloud file storage API — TC-15 (upload), TC-16 (retrieve), TC-17 (invalid file) and
TC-20 (storage outage), plus saving plan exports to object storage."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.app import create_app
from backend.models.db_models import UserFile
from tests.helpers import (
    JPEG_BYTES,
    PDF_BYTES,
    auth_headers,
    complete_profile,
    make_settings,
    png_bytes,
    register,
    upload,
)


@pytest.fixture
def user(client) -> dict:
    return register(client)


@pytest.fixture
def token(user) -> str:
    return user["access_token"]


# --- TC-15: upload file -------------------------------------------------------------------------
def test_tc15_meal_image_upload_is_stored_in_object_storage(client, app, user, token):
    image = png_bytes()

    response = upload(client, token, "my lunch.png", image, "image/png")

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "my lunch.png"
    assert body["content_type"] == "image/png"
    assert body["size_bytes"] == len(image)
    assert body["category"] == "meal_image"
    with app.state.db.session_factory() as db:
        key = db.scalar(select(UserFile.storage_path).where(UserFile.id == body["id"]))
    assert key.startswith(f"users/{user['user']['id']}/meal-images/")
    assert app.state.storage.download(key) == image


@pytest.mark.parametrize(
    ("filename", "data", "content_type", "category"),
    [
        ("breakfast.jpg", JPEG_BYTES, "image/jpeg", "meal_image"),
        ("sample-plan.pdf", PDF_BYTES, "application/pdf", "document"),
    ],
)
def test_jpeg_images_and_pdf_documents_are_accepted(client, token, filename, data,
                                                    content_type, category):
    response = upload(client, token, filename, data)

    assert response.status_code == 201
    assert response.json()["content_type"] == content_type
    assert response.json()["category"] == category


def test_upload_requires_authentication(client):
    response = client.post("/api/upload", files={"file": ("a.png", png_bytes(), "image/png")})

    assert response.status_code == 401


# --- TC-16: retrieve file -----------------------------------------------------------------------
def test_tc16_uploaded_files_are_listed_and_download_byte_for_byte(client, token):
    image = png_bytes(4, 4)
    file_id = upload(client, token, "dinner.png", image).json()["id"]

    listing = client.get("/api/files", headers=auth_headers(token)).json()
    download = client.get(f"/api/files/{file_id}/download", headers=auth_headers(token))

    assert listing["total"] == 1
    assert listing["total_bytes"] == len(image)
    assert listing["items"][0]["download_url"] == f"/api/files/{file_id}/download"
    assert download.status_code == 200
    assert download.content == image
    assert download.headers["content-type"] == "image/png"
    assert 'filename="dinner.png"' in download.headers["content-disposition"]


# --- TC-17: invalid file -------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("filename", "data", "status", "code"),
    [
        ("notes.txt", b"just some text", 415, "unsupported_media_type"),
        ("setup.exe", b"MZ\x90\x00" + b"\x00" * 60, 415, "unsupported_media_type"),
        ("drawing.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>', 415,
         "unsupported_media_type"),
        ("fake.png", JPEG_BYTES, 415, "file_type_mismatch"),  # extension lies about content
        ("photo.png.html", png_bytes(), 415, "file_type_mismatch"),
        ("empty.png", b"", 400, "empty_file"),
    ],
)
def test_tc17_invalid_files_are_rejected(client, token, filename, data, status, code):
    response = upload(client, token, filename, data)

    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_tc17_files_over_the_size_limit_are_rejected(tmp_path):
    app = create_app(make_settings(tmp_path, max_upload_mb=0.001))  # about 1 KB
    with TestClient(app) as client:
        token = register(client)["access_token"]
        response = upload(client, token, "big.png", png_bytes() + b"\x00" * 2048)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_path_components_in_filenames_are_stripped(client, app, token):
    body = upload(client, token, "../../etc/passwd.png", png_bytes()).json()

    with app.state.db.session_factory() as db:
        key = db.scalar(select(UserFile.storage_path).where(UserFile.id == body["id"]))
    assert body["filename"] == "passwd.png"
    assert ".." not in key


def test_per_user_storage_quota_is_enforced(tmp_path):
    app = create_app(make_settings(tmp_path, max_files_per_user=2))
    with TestClient(app) as client:
        token = register(client)["access_token"]
        statuses = [upload(client, token, f"meal-{i}.png", png_bytes()).status_code
                    for i in range(3)]
        blocked = upload(client, token, "meal-3.png", png_bytes())

    assert statuses == [201, 201, 403]
    assert blocked.json()["error"]["code"] == "storage_quota_exceeded"


# --- Delete --------------------------------------------------------------------------------------
def test_deleting_a_file_removes_the_object_and_its_metadata(client, app, token):
    file_id = upload(client, token, "gone.png", png_bytes()).json()["id"]
    with app.state.db.session_factory() as db:
        key = db.scalar(select(UserFile.storage_path).where(UserFile.id == file_id))

    response = client.delete(f"/api/files/{file_id}", headers=auth_headers(token))

    assert response.status_code == 204
    assert not app.state.storage.exists(key)
    assert client.get("/api/files", headers=auth_headers(token)).json()["total"] == 0
    assert client.get(f"/api/files/{file_id}/download",
                      headers=auth_headers(token)).status_code == 404


# --- Plan exports saved to object storage --------------------------------------------------------
def test_a_plan_can_be_saved_to_cloud_storage_as_a_file(client, token):
    complete_profile(client, token)
    plan = client.post("/api/generate-plan", json={}, headers=auth_headers(token)).json()

    response = client.post(f"/api/plans/{plan['id']}/save-to-cloud?format=txt",
                           headers=auth_headers(token))

    assert response.status_code == 201
    saved = response.json()
    assert saved["category"] == "plan_export"
    assert saved["plan_id"] == plan["id"]
    assert saved["filename"].endswith(".txt")
    content = client.get(saved["download_url"], headers=auth_headers(token)).text
    assert plan["title"] in content


def test_deleting_a_plan_keeps_its_saved_export_but_unlinks_it(client, token):
    complete_profile(client, token)
    plan = client.post("/api/generate-plan", json={}, headers=auth_headers(token))
    plan_id = plan.json()["id"]
    client.post(f"/api/plans/{plan_id}/save-to-cloud?format=json", headers=auth_headers(token))

    client.delete(f"/api/plans/{plan_id}", headers=auth_headers(token))
    files = client.get("/api/files", headers=auth_headers(token)).json()

    assert files["total"] == 1
    assert files["items"][0]["plan_id"] is None


# --- TC-20: cloud storage failure handling -------------------------------------------------------
@pytest.fixture
def broken_storage_app(tmp_path):
    """Real OS errors, not mocks: a file sits where the storage bucket directory should be."""
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    (storage_root / "diet-planner-files").write_text("not a directory")
    return create_app(make_settings(tmp_path, local_storage_dir=str(storage_root)))


def test_tc20_storage_outage_returns_503_and_keeps_the_database_consistent(broken_storage_app):
    with TestClient(broken_storage_app) as client:
        token = register(client)["access_token"]
        response = upload(client, token, "meal.png", png_bytes())
        files = client.get("/api/files", headers=auth_headers(token)).json()
        ready = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_unavailable"
    assert files["total"] == 0  # no metadata row for an object that was never stored
    assert ready.status_code == 503
    assert ready.json()["checks"]["storage"] == "unavailable"


def test_object_is_removed_again_when_its_metadata_cannot_be_saved(client, app, token,
                                                                   monkeypatch):
    # The database fails *after* the bytes reached object storage. Without the compensating
    # delete, the object would be orphaned: stored (and billed) but invisible to everyone.
    real_commit = Session.commit

    def commit_that_fails_for_new_files(session):
        if any(isinstance(item, UserFile) for item in session.new):
            raise OperationalError("INSERT INTO user_files", {}, Exception("database went away"))
        return real_commit(session)

    monkeypatch.setattr(Session, "commit", commit_that_fails_for_new_files)

    response = upload(client, token, "meal.png", png_bytes())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert not [path for path in app.state.storage.bucket_dir.rglob("*") if path.is_file()]


def test_system_status_reports_the_storage_provider(client):
    assert client.get("/api/system/status").json()["storage_provider"] == "local"
