"""Cloud file logic: validate, store the bytes in object storage and the metadata in the
database, and keep the two consistent.

There is no transaction spanning a database and a bucket, so the order of operations matters:

* **upload** — write the object first, then the metadata row. If the row cannot be saved,
  delete the object again (a *compensating action*), so no invisible orphan is left behind.
* **delete** — delete the object first, then the row. If storage is down the row stays, the
  user sees an error and can simply retry.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models.db_models import UserFile
from backend.models.schemas import PlanOut
from backend.services import export_service
from backend.utils.errors import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from backend.utils.file_validation import (
    SUPPORTED_DESCRIPTION,
    detect_file_type,
    extension_of,
    sanitize_filename,
)
from cloud.storage_service import (
    StorageError,
    StorageObjectNotFound,
    StorageService,
    build_object_key,
)

logger = logging.getLogger("diet_planner.files")


def _check_quota(db: Session, user_id: str, max_files: int) -> None:
    count = db.scalar(select(func.count()).select_from(UserFile).where(UserFile.user_id == user_id))
    if (count or 0) >= max_files:
        raise ForbiddenError(
            f"You have reached the limit of {max_files} stored files. Delete some to upload more.",
            code="storage_quota_exceeded",
        )


def store_user_file(
    db: Session,
    storage: StorageService,
    *,
    user_id: str,
    filename: str,
    data: bytes,
    content_type: str,
    category: str,
    folder: str,
    extension: str,
    max_files: int,
    plan_id: str | None = None,
) -> UserFile:
    _check_quota(db, user_id, max_files)
    key = build_object_key(user_id, folder, extension)
    storage.upload(key, data, content_type)  # StorageError -> HTTP 503

    record = UserFile(
        user_id=user_id,
        filename=filename,
        storage_path=key,
        content_type=content_type,
        size_bytes=len(data),
        category=category,
        plan_id=plan_id,
    )
    db.add(record)
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            storage.delete(key)  # compensating action: don't leave an orphaned object
        except StorageError:
            logger.error("Could not remove orphaned object %s", key)
        raise
    db.refresh(record)
    return record


def upload_user_file(
    db: Session,
    storage: StorageService,
    user_id: str,
    raw_filename: str | None,
    data: bytes,
    *,
    max_bytes: int,
    max_files: int,
) -> UserFile:
    if not data:
        raise BadRequestError("The uploaded file is empty.", code="empty_file")
    if len(data) > max_bytes:
        raise PayloadTooLargeError(f"Files must be {max_bytes / (1024 * 1024):g} MB or smaller.")
    file_type = detect_file_type(data)
    if file_type is None:
        raise UnsupportedMediaTypeError(f"Only {SUPPORTED_DESCRIPTION} can be uploaded.")

    filename = sanitize_filename(raw_filename, file_type.extension)
    declared = extension_of(filename)
    if not declared:
        filename += file_type.extension
    elif declared not in file_type.allowed_extensions:
        raise UnsupportedMediaTypeError(
            f"The file extension '{declared}' does not match its content ({file_type.mime}).",
            code="file_type_mismatch",
        )

    return store_user_file(
        db,
        storage,
        user_id=user_id,
        filename=filename,
        data=data,
        content_type=file_type.mime,
        category=file_type.category,
        folder=file_type.folder,
        extension=file_type.extension,
        max_files=max_files,
    )


def save_plan_export(
    db: Session, storage: StorageService, user_id: str, plan: PlanOut, export_format: str,
    *, max_files: int,
) -> UserFile:
    """Store a JSON or text export of a plan in object storage, linked to the plan."""
    data = (export_service.plan_to_json(plan) if export_format == "json"
            else export_service.plan_to_text(plan).encode("utf-8"))
    return store_user_file(
        db,
        storage,
        user_id=user_id,
        filename=export_service.export_filename(plan, export_format),
        data=data,
        content_type=export_service.EXPORT_MEDIA_TYPES[export_format],
        category="plan_export",
        folder="plan-exports",
        extension=f".{export_format}",
        max_files=max_files,
        plan_id=plan.id,
    )


def list_user_files(db: Session, user_id: str) -> list[UserFile]:
    return list(db.scalars(
        select(UserFile)
        .where(UserFile.user_id == user_id)
        .order_by(UserFile.uploaded_at.desc(), UserFile.id.desc())
    ).all())


def get_user_file(db: Session, user_id: str, file_id: str) -> UserFile:
    """Owner-scoped lookup: someone else's file is reported as 'not found'."""
    record = db.scalar(
        select(UserFile).where(UserFile.id == file_id, UserFile.user_id == user_id)
    )
    if record is None:
        raise NotFoundError("File not found.")
    return record


def read_user_file(
    db: Session, storage: StorageService, user_id: str, file_id: str
) -> tuple[UserFile, bytes]:
    record = get_user_file(db, user_id, file_id)
    try:
        return record, storage.download(record.storage_path)
    except StorageObjectNotFound as exc:
        raise NotFoundError("The file's content is missing from storage.",
                            code="file_content_missing") from exc


def delete_user_file(db: Session, storage: StorageService, user_id: str, file_id: str) -> None:
    record = get_user_file(db, user_id, file_id)
    storage.delete(record.storage_path)  # StorageError -> 503, metadata kept for a retry
    db.delete(record)
    db.commit()
