"""Object storage adapters: the local simulated bucket and the S3-compatible adapter.

The S3 adapter runs against moto — an in-memory implementation of the AWS S3 API — so the
exact boto3 calls used in production are exercised without an AWS account.
"""

import boto3
import pytest
from moto import mock_aws

from cloud.storage_service import (
    LocalStorageService,
    S3StorageService,
    StorageError,
    StorageObjectNotFound,
    build_object_key,
)

FAKE_AWS = {"access_key_id": "testing", "secret_access_key": "testing"}  # moto accepts any
KEY = "users/123e4567-e89b-12d3-a456-426614174000/meal-images/photo.png"


@pytest.fixture
def local(tmp_path) -> LocalStorageService:
    return LocalStorageService(root_dir=tmp_path, bucket="test-bucket")


@pytest.fixture
def s3():
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="diet-planner-test")
        yield S3StorageService(bucket="diet-planner-test", region="us-east-1", **FAKE_AWS)


@pytest.fixture(params=["local", "s3"])
def storage(request, local, s3):
    return {"local": local, "s3": s3}[request.param]


def test_objects_round_trip_byte_for_byte(storage):
    storage.upload(KEY, b"\x89PNG demo bytes", "image/png")

    assert storage.exists(KEY)
    assert storage.download(KEY) == b"\x89PNG demo bytes"


def test_deleted_objects_are_gone(storage):
    storage.upload(KEY, b"data", "image/png")

    storage.delete(KEY)

    assert not storage.exists(KEY)
    with pytest.raises(StorageObjectNotFound):
        storage.download(KEY)


def test_deleting_a_missing_object_is_harmless(storage):
    storage.delete("users/nobody/meal-images/missing.png")


def test_health_check_passes_when_the_bucket_is_reachable(storage):
    assert storage.health_check() is True


@pytest.mark.parametrize(
    "bad_key",
    ["../outside.png", "users/../../etc/passwd", "/absolute/path.png", "users//double.png",
     "users\\windows\\path.png", ""],
)
def test_path_traversal_and_malformed_keys_are_rejected(local, bad_key):
    with pytest.raises(StorageError):
        local.upload(bad_key, b"x", "image/png")


def test_local_bucket_lives_under_the_configured_root(local, tmp_path):
    local.upload(KEY, b"data", "image/png")

    assert (tmp_path / "test-bucket" / KEY).read_bytes() == b"data"


def test_s3_objects_carry_their_content_type(s3):
    s3.upload(KEY, b"%PDF-1.4", "application/pdf")

    head = s3.client.head_object(Bucket="diet-planner-test", Key=KEY)

    assert head["ContentType"] == "application/pdf"


def test_s3_health_check_fails_when_the_bucket_does_not_exist():
    with mock_aws():
        missing = S3StorageService(bucket="no-such-bucket", region="us-east-1", **FAKE_AWS)

        assert missing.health_check() is False


def test_s3_errors_are_translated_into_storage_errors():
    with mock_aws():
        missing = S3StorageService(bucket="no-such-bucket", region="us-east-1", **FAKE_AWS)

        with pytest.raises(StorageError):
            missing.upload(KEY, b"data", "image/png")


def test_object_keys_are_namespaced_per_user_and_unguessable():
    first = build_object_key("user-1", "meal-images", ".png")
    second = build_object_key("user-1", "meal-images", ".png")

    assert first.startswith("users/user-1/meal-images/")
    assert first.endswith(".png")
    assert first != second
