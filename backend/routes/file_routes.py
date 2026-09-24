"""Cloud file endpoints: upload, list, download and delete files in object storage."""

import logging
from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile, status

from backend.config import API_PREFIX
from backend.models.schemas import FileList, FileOut
from backend.services import file_service
from backend.utils.dependencies import AppMetrics, AppSettings, CurrentUser, DbSession, Storage

logger = logging.getLogger("diet_planner.files")

router = APIRouter(prefix=API_PREFIX, tags=["Cloud files"])


@router.post(
    "/upload",
    response_model=FileOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a meal image (JPEG/PNG/WebP) or PDF to cloud storage",
    responses={
        400: {"description": "Empty file"},
        403: {"description": "Storage quota reached"},
        413: {"description": "File larger than MAX_UPLOAD_MB"},
        415: {"description": "Unsupported type, or extension does not match content"},
        503: {"description": "Object storage unavailable"},
    },
)
def upload_file(
    file: Annotated[UploadFile, File(description="JPEG, PNG, WebP or PDF")],
    user: CurrentUser,
    db: DbSession,
    storage: Storage,
    settings: AppSettings,
    metrics: AppMetrics,
) -> FileOut:
    # Read at most one byte more than allowed: enough to detect an oversized upload
    # without loading an arbitrarily large body into memory.
    data = file.file.read(settings.max_upload_bytes + 1)
    record = file_service.upload_user_file(
        db, storage, user.id, file.filename, data,
        max_bytes=settings.max_upload_bytes, max_files=settings.max_files_per_user,
    )
    metrics.inc("files_uploaded_total", category=record.category)
    logger.info("File stored", extra={"user_id": user.id, "file_id": record.id,
                                      "size_bytes": record.size_bytes})
    return FileOut.model_validate(record)


@router.get("/files", response_model=FileList, summary="List my stored files")
def list_files(user: CurrentUser, db: DbSession, settings: AppSettings) -> FileList:
    records = file_service.list_user_files(db, user.id)
    return FileList(
        items=[FileOut.model_validate(record) for record in records],
        total=len(records),
        total_bytes=sum(record.size_bytes for record in records),
        max_files=settings.max_files_per_user,
        max_upload_mb=settings.max_upload_mb,
    )


@router.get(
    "/files/{file_id}/download",
    summary="Download one of my files",
    response_class=Response,
    responses={404: {"description": "No such file for this user"}},
)
def download_file(file_id: str, user: CurrentUser, db: DbSession, storage: Storage) -> Response:
    record, data = file_service.read_user_file(db, storage, user.id, file_id)
    return Response(
        content=data,
        media_type=record.content_type,
        headers={"Content-Disposition": f'attachment; filename="{record.filename}"'},
    )


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete one of my files",
               responses={404: {"description": "No such file for this user"}})
def delete_file(file_id: str, user: CurrentUser, db: DbSession, storage: Storage) -> Response:
    file_service.delete_user_file(db, storage, user.id, file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
