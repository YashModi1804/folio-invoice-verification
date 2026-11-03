from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.db import DocumentSource
from app.parser import DocumentError, parse

EXTENSIONS = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def inspect(data: bytes, filename: str) -> tuple[str, int]:
    if not data or len(data) > settings.max_file_bytes:
        raise DocumentError("FILE_SIZE_LIMIT")
    expected = EXTENSIONS.get(Path(filename).suffix.lower())
    if expected is None:
        raise DocumentError("UNSUPPORTED_FILE_TYPE")
    return parse(data, "inspect", media_type=expected)


def document_path(job_id: str) -> Path:
    return settings.storage_dir / f"{job_id}.bin"


def save_source(db, job_id: str, data: bytes) -> None:
    if settings.source_storage == "database":
        db.add(DocumentSource(job_id=job_id, content=data))
        return
    path = document_path(job_id)
    path.write_bytes(data)
    path.chmod(0o600)


def read_source(db, job_id: str) -> bytes | None:
    if settings.source_storage == "database":
        source = db.get(DocumentSource, job_id)
        return source.content if source else None
    path = document_path(job_id)
    return path.read_bytes() if path.exists() else None


def source_exists(db, job_id: str) -> bool:
    if settings.source_storage == "database":
        return (
            db.scalar(select(DocumentSource.job_id).where(DocumentSource.job_id == job_id))
            is not None
        )
    return document_path(job_id).exists()


def delete_source(db, job_id: str) -> bool:
    if settings.source_storage == "database":
        source = db.get(DocumentSource, job_id)
        if source is None:
            return False
        db.delete(source)
        return True
    path = document_path(job_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def render(
    data: bytes, media_type: str, page_numbers: tuple[int, ...] | None = None
) -> list[bytes]:
    return parse(data, "render", media_type=media_type, page_numbers=page_numbers)


def page_texts(data: bytes, media_type: str) -> list[str]:
    """Return native PDF text for local planning; never use it as trusted extraction data."""
    return parse(data, "text", media_type=media_type)
