"""Cloud object storage service.

Object storage keeps *files* (meal photos, PDFs, exported plans) as immutable objects in a
flat namespace called a bucket, addressed by a key such as::

    users/<user-id>/meal-images/<random-uuid>.png

It is cheap, virtually unlimited and served over HTTP — unlike a database, which stores
structured rows you can query. The app keeps the file's *metadata* (owner, name, size, type,
key) in the database and the *bytes* here.

Two interchangeable implementations share one interface:

* ``LocalStorageService`` — a folder on disk that mimics a bucket (local development);
* ``S3StorageService``    — any S3-compatible service: AWS S3, Supabase Storage,
  Cloudflare R2, MinIO, Backblaze B2 …

Switch with ``STORAGE_PROVIDER=local|s3`` — no code changes.
"""

import logging
import os
import re
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger("diet_planner.storage")

# Conservative key grammar: letters, digits and / _ . - only; no "..", no "//", no leading "/".
_VALID_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/_.\-]{0,511}$")


class StorageError(Exception):
    """The storage service failed or is unreachable."""


class StorageObjectNotFound(StorageError):
    """No object exists under the requested key."""


def validate_key(key: str) -> str:
    if not _VALID_KEY.match(key) or ".." in key or "//" in key:
        raise StorageError(f"Invalid object key: {key!r}")
    return key


def build_object_key(user_id: str, folder: str, extension: str) -> str:
    """Per-user prefix + random name. The user-supplied filename never becomes part of the key,
    which rules out path traversal and makes keys unguessable."""
    return validate_key(f"users/{user_id}/{folder}/{uuid.uuid4().hex}{extension}")


class StorageService(ABC):
    provider_name: str
    bucket: str

    @abstractmethod
    def upload(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    def download(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def health_check(self) -> bool: ...


class LocalStorageService(StorageService):
    """A bucket simulated as a directory: ``<root_dir>/<bucket>/<key>``."""

    provider_name = "local"

    def __init__(self, root_dir: Path, bucket: str) -> None:
        self.bucket = bucket
        self.bucket_dir = (Path(root_dir) / bucket).resolve()

    def _path(self, key: str) -> Path:
        path = (self.bucket_dir / validate_key(key)).resolve()
        if self.bucket_dir not in path.parents:  # defence in depth against traversal
            raise StorageError(f"Invalid object key: {key!r}")
        return path

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        temporary = path.with_name(path.name + ".part")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(data)
            os.replace(temporary, path)  # atomic: readers never see a half-written object
        except OSError as exc:
            raise StorageError(f"Local storage write failed: {exc.__class__.__name__}") from exc

    def download(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise StorageObjectNotFound(key) from exc
        except OSError as exc:
            raise StorageError(f"Local storage read failed: {exc.__class__.__name__}") from exc

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError(f"Local storage delete failed: {exc.__class__.__name__}") from exc

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def health_check(self) -> bool:
        try:
            self.bucket_dir.mkdir(parents=True, exist_ok=True)
            return os.access(self.bucket_dir, os.W_OK)
        except OSError:
            return False


class S3StorageService(StorageService):
    """Amazon S3 API via boto3. Also works with any S3-compatible provider through
    ``endpoint_url`` (Supabase Storage, Cloudflare R2, MinIO…).

    Credentials: if no keys are given, boto3's default chain is used — on AWS that means the
    IAM role attached to the compute (App Runner / ECS / Lambda), so no secret is stored at all.
    """

    provider_name = "s3"

    def __init__(
        self,
        bucket: str,
        *,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        force_path_style: bool = False,
    ) -> None:
        import boto3  # imported lazily: only needed when STORAGE_PROVIDER=s3
        from botocore.config import Config

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path" if force_path_style else "auto"},
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=30,
            ),
        )

    @staticmethod
    def _is_not_found(exc: Exception) -> bool:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        return code in ("404", "NoSuchKey", "NotFound")

    def _translate(self, exc: Exception, action: str) -> StorageError:
        logger.warning("S3 %s failed: %s", action, exc.__class__.__name__)
        return StorageError(f"S3 {action} failed: {exc.__class__.__name__}")

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            self.client.put_object(
                Bucket=self.bucket, Key=validate_key(key), Body=data, ContentType=content_type
            )
        except (BotoCoreError, ClientError) as exc:
            raise self._translate(exc, "upload") from exc

    def download(self, key: str) -> bytes:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            response = self.client.get_object(Bucket=self.bucket, Key=validate_key(key))
            return response["Body"].read()
        except ClientError as exc:
            if self._is_not_found(exc):
                raise StorageObjectNotFound(key) from exc
            raise self._translate(exc, "download") from exc
        except BotoCoreError as exc:
            raise self._translate(exc, "download") from exc

    def delete(self, key: str) -> None:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            self.client.delete_object(Bucket=self.bucket, Key=validate_key(key))
        except (BotoCoreError, ClientError) as exc:
            raise self._translate(exc, "delete") from exc

    def exists(self, key: str) -> bool:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=validate_key(key))
            return True
        except ClientError as exc:
            if self._is_not_found(exc):
                return False
            raise self._translate(exc, "head") from exc
        except BotoCoreError as exc:
            raise self._translate(exc, "head") from exc

    def health_check(self) -> bool:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except (BotoCoreError, ClientError) as exc:
            logger.warning("S3 health check failed: %s", exc.__class__.__name__)
            return False


def create_storage_service(
    provider: str,
    *,
    bucket: str,
    local_dir: Path,
    region: str = "us-east-1",
    endpoint_url: str | None = None,
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
    force_path_style: bool = False,
) -> StorageService:
    """Factory used by the application: pick the implementation from configuration."""
    if provider == "s3":
        return S3StorageService(
            bucket,
            region=region,
            endpoint_url=endpoint_url,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            force_path_style=force_path_style,
        )
    if provider == "local":
        return LocalStorageService(root_dir=local_dir, bucket=bucket)
    raise ValueError(f"Unknown storage provider: {provider!r}")
