from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image, UnidentifiedImageError

from app.config import settings

Image.MAX_IMAGE_PIXELS = 25_000_000
EXTENSIONS = {".pdf": "application/pdf", ".png": "image/png",
              ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


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
    except (RuntimeError, ValueError, OSError, UnidentifiedImageError,
            Image.DecompressionBombError) as exc:
        raise DocumentError("CORRUPT_DOCUMENT") from exc


def document_path(job_id: str) -> Path:
    return settings.storage_dir / f"{job_id}.bin"


def render(data: bytes, media_type: str) -> list[bytes]:
    if media_type == "application/pdf":
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            return [page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).tobytes("png")
                    for page in doc]
    with Image.open(BytesIO(data)) as image:
        image.thumbnail((2400, 2400))
        output = BytesIO()
        image.convert("RGB").save(output, format="PNG")
        return [output.getvalue()]
