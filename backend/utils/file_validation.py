"""Upload validation.

Never trust what the client says about a file: the filename and Content-Type header are
chosen by the uploader. Instead, the first bytes of the file ("magic numbers") are inspected
to detect the real type, and only an allow-list of harmless types is accepted. SVG, HTML and
executables are rejected because browsers or operating systems can run code inside them.
"""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class FileType:
    mime: str
    extension: str  # canonical extension, used when the upload has none
    allowed_extensions: frozenset[str]
    category: str  # meal_image | document
    folder: str  # object-storage folder under users/<id>/


JPEG = FileType("image/jpeg", ".jpg", frozenset({".jpg", ".jpeg"}), "meal_image", "meal-images")
PNG = FileType("image/png", ".png", frozenset({".png"}), "meal_image", "meal-images")
WEBP = FileType("image/webp", ".webp", frozenset({".webp"}), "meal_image", "meal-images")
PDF = FileType("application/pdf", ".pdf", frozenset({".pdf"}), "document", "documents")

SUPPORTED_DESCRIPTION = "JPEG, PNG or WebP images and PDF documents"

_UNSAFE_CHARACTERS = re.compile(r"[^A-Za-z0-9 ._()\-]+")
MAX_FILENAME_LENGTH = 100


def detect_file_type(data: bytes) -> FileType | None:
    """Identify the file from its signature bytes."""
    if data.startswith(b"\xff\xd8\xff"):
        return JPEG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return WEBP
    if data.startswith(b"%PDF-"):
        return PDF
    return None


def sanitize_filename(raw: str | None, fallback_extension: str) -> str:
    """A safe *display* name: no directories, no control or special characters, bounded
    length. It is only shown to the user — storage keys are random UUIDs."""
    name = PurePosixPath((raw or "").replace("\\", "/")).name
    name = _UNSAFE_CHARACTERS.sub("_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name or name.startswith("."):
        name = f"file{fallback_extension}"
    if len(name) > MAX_FILENAME_LENGTH:
        suffix = PurePosixPath(name).suffix[:10]
        name = name[: MAX_FILENAME_LENGTH - len(suffix)] + suffix
    return name


def extension_of(filename: str) -> str:
    return PurePosixPath(filename).suffix.lower()
