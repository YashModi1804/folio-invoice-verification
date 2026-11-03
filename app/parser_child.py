"""Standalone child entry point. Do not import application settings or credentials."""

import json
import math
import resource
import sys
from io import BytesIO

HEADER_LIMIT = 16 * 1024
TEXT_LIMIT = 256 * 1024
PAGE_TEXT_LIMIT = 64 * 1024
PIXEL_LIMIT = 25_000_000


class Rejected(Exception):
    pass


def set_limits(cpu: int, memory_mb: int, output_limit: int) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (output_limit + HEADER_LIMIT,) * 2)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # macOS RLIMIT_AS does not reliably constrain native allocations; wall/CPU/output
    # limits still apply there. Linux deployments enforce this address-space ceiling.
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 1024 * 1024,) * 2)


def process(data: bytes, request: dict, max_pages: int, output_limit: int):
    import pymupdf
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = PIXEL_LIMIT
    pymupdf.TOOLS.mupdf_display_errors(False)
    pymupdf.TOOLS.mupdf_display_warnings(False)
    operation, expected = request["operation"], request["media_type"]
    selected = request.get("page_numbers")
    if operation not in {"inspect", "render", "text"}:
        raise Rejected("PARSER_FAILED")
    if data.startswith(b"%PDF-"):
        actual = "application/pdf"
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass:
                raise Rejected("PASSWORD_PROTECTED_PDF")
            if not 1 <= len(doc) <= max_pages:
                raise Rejected("PAGE_LIMIT")
            for page in doc:
                width, height = page.rect.width, page.rect.height
                if (
                    not math.isfinite(width * height)
                    or min(width, height) <= 0
                    or max(width, height) > 5000
                    or width * height * 4 > PIXEL_LIMIT
                ):
                    raise Rejected("PAGE_DIMENSIONS_LIMIT")
            if expected != actual:
                raise Rejected("CONTENT_TYPE_MISMATCH")
            if operation == "inspect":
                return {"media_type": actual, "pages": len(doc)}, b""
            if operation == "text":
                texts, remaining = [], TEXT_LIMIT
                for page in doc:
                    text = page.get_text()
                    if len(text) > min(PAGE_TEXT_LIMIT, remaining):
                        raise Rejected("PARSER_OUTPUT_LIMIT")
                    texts.append(text)
                    remaining -= len(text)
                return {}, json.dumps(texts, ensure_ascii=False).encode()
            numbers = selected if selected is not None else list(range(1, len(doc) + 1))
            if (
                not numbers
                or len(numbers) > max_pages
                or any(type(number) is not int or not 1 <= number <= len(doc) for number in numbers)
                or len(set(numbers)) != len(numbers)
            ):
                raise Rejected("PAGE_NOT_FOUND")
            images, size = [], 0
            for number in numbers:
                pixmap = doc[number - 1].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
                image = pixmap.tobytes("png")
                del pixmap
                size += len(image)
                if size > output_limit:
                    raise Rejected("PARSER_OUTPUT_LIMIT")
                images.append(image)
            return {"lengths": [len(image) for image in images]}, b"".join(images)
    with Image.open(BytesIO(data)) as image:
        if image.width * image.height > PIXEL_LIMIT or max(image.width, image.height) > 10_000:
            raise Rejected("IMAGE_DIMENSIONS_LIMIT")
        if getattr(image, "n_frames", 1) != 1:
            raise Rejected("ANIMATED_IMAGE_UNSUPPORTED")
        actual = Image.MIME.get(image.format)
        if actual != expected:
            raise Rejected("CONTENT_TYPE_MISMATCH")
        if operation == "inspect":
            image.verify()
            return {"media_type": actual, "pages": 1}, b""
        if operation == "text":
            return {}, b'[""]'
        if selected is not None and selected != [1]:
            raise Rejected("PAGE_NOT_FOUND")
        image.thumbnail((2400, 2400))
        output = BytesIO()
        image.convert("RGB").save(output, format="PNG")
        rendered = output.getvalue()
        if len(rendered) > output_limit:
            raise Rejected("PARSER_OUTPUT_LIMIT")
        return {"lengths": [len(rendered)]}, rendered


def main():
    try:
        cpu, memory_mb, input_limit, max_pages, output_limit = map(int, sys.argv[1:])
        set_limits(cpu, memory_mb, output_limit)
        header = sys.stdin.buffer.readline(HEADER_LIMIT + 1)
        if not header.endswith(b"\n") or len(header) > HEADER_LIMIT:
            raise Rejected("PARSER_FAILED")
        request = json.loads(header)
        data = sys.stdin.buffer.read(input_limit + 1)
        if not data or len(data) > input_limit:
            raise Rejected("FILE_SIZE_LIMIT")
        metadata, payload = process(data, request, max_pages, output_limit)
        if len(payload) > output_limit:
            raise Rejected("PARSER_OUTPUT_LIMIT")
        result = {"operation": request["operation"], **metadata}
    except Rejected as exc:
        result, payload = {"error": str(exc)}, b""
    except MemoryError:
        result, payload = {"error": "PARSER_RESOURCE_LIMIT"}, b""
    except Exception:
        result, payload = {"error": "CORRUPT_DOCUMENT"}, b""
    sys.stdout.buffer.write(json.dumps(result).encode() + b"\n" + payload)


if __name__ == "__main__":
    main()
