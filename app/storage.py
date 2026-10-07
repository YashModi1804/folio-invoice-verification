from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select

from app.config import settings
from app.db import DocumentSource

Image.MAX_IMAGE_PIXELS = 25_000_000
EXTENSIONS = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class DocumentError(ValueError):
    pass


def inspect(data: bytes, filename: str) -> tuple[str, int]:
    if not data or len(data) > settings.max_file_bytes:
        raise DocumentError("FILE_SIZE_LIMIT")
    expected = EXTENSIONS.get(Path(filename).suffix.lower())
    if expected is None:
        raise DocumentError("UNSUPPORTED_FILE_TYPE")
    try:
        if data.startswith(b"%PDF-"):
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                if doc.needs_pass:
                    raise DocumentError("PASSWORD_PROTECTED_PDF")
                if not 1 <= len(doc) <= settings.max_pages:
                    raise DocumentError("PAGE_LIMIT")
                for page in doc:
                    if page.rect.width * page.rect.height * 4 > 25_000_000:
                        raise DocumentError("PAGE_DIMENSIONS_LIMIT")
                actual, pages = "application/pdf", len(doc)
        else:
            with Image.open(BytesIO(data)) as image:
                actual, pages = Image.MIME.get(image.format), 1
                if image.width * image.height > Image.MAX_IMAGE_PIXELS:
                    raise DocumentError("IMAGE_DIMENSIONS_LIMIT")
                if getattr(image, "n_frames", 1) != 1:
                    raise DocumentError("ANIMATED_IMAGE_UNSUPPORTED")
                image.verify()
        if actual != expected:
            raise DocumentError("CONTENT_TYPE_MISMATCH")
        return actual, pages
    except DocumentError:
        raise
    except (
        RuntimeError,
        ValueError,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ) as exc:
        raise DocumentError("CORRUPT_DOCUMENT") from exc


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
    if media_type == "application/pdf":
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            selected = page_numbers or tuple(range(1, len(doc) + 1))
            return [
                doc[page_number - 1]
                .get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
                .tobytes("png")
                for page_number in selected
            ]
    if page_numbers and page_numbers != (1,):
        raise DocumentError("PAGE_NOT_FOUND")
    with Image.open(BytesIO(data)) as image:
        image.thumbnail((2400, 2400))
        output = BytesIO()
        image.convert("RGB").save(output, format="PNG")
        return [output.getvalue()]


def page_texts(data: bytes, media_type: str) -> list[str]:
    """Return native PDF text for local planning; never use it as trusted extraction data."""
    if media_type != "application/pdf":
        return [""]
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [page.get_text() for page in doc]
