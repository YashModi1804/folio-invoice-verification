"""Resource-bounded native parsing; this is not an operating-system sandbox."""

import json
import signal
import struct
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryFile
from threading import BoundedSemaphore

from app.config import settings

HEADER_LIMIT = 16 * 1024
TEXT_LIMIT = 256 * 1024
_slot = BoundedSemaphore(1)
_child = Path(__file__).with_name("parser_child.py")
ERROR_CODES = frozenset(
    {
        "FILE_SIZE_LIMIT",
        "UNSUPPORTED_FILE_TYPE",
        "PASSWORD_PROTECTED_PDF",
        "PAGE_LIMIT",
        "PAGE_DIMENSIONS_LIMIT",
        "IMAGE_DIMENSIONS_LIMIT",
        "ANIMATED_IMAGE_UNSUPPORTED",
        "CONTENT_TYPE_MISMATCH",
        "CORRUPT_DOCUMENT",
        "PAGE_NOT_FOUND",
        "PARSER_RESOURCE_LIMIT",
        "PARSER_OUTPUT_LIMIT",
        "PARSER_FAILED",
    }
)


class DocumentError(ValueError):
    pass


def _decode(output: bytes, operation: str):
    header, separator, payload = output.partition(b"\n")
    if not separator or len(header) > HEADER_LIMIT:
        raise DocumentError("PARSER_FAILED")
    try:
        result = json.loads(header)
        if not isinstance(result, dict):
            raise ValueError
        if result.get("error") in ERROR_CODES and not payload:
            raise DocumentError(result["error"])
        if result.get("operation") != operation:
            raise ValueError
        if operation == "inspect":
            media_type, pages = result["media_type"], result["pages"]
            if media_type not in {"application/pdf", "image/png", "image/jpeg", "image/webp"}:
                raise ValueError
            if type(pages) is not int or not 1 <= pages <= settings.max_pages or payload:
                raise ValueError
            return media_type, pages
        if operation == "text":
            texts = json.loads(payload)
            if (
                not isinstance(texts, list)
                or not 1 <= len(texts) <= settings.max_pages
                or any(not isinstance(text, str) for text in texts)
                or sum(len(text) for text in texts) > TEXT_LIMIT
            ):
                raise ValueError
            return texts
        lengths = result["lengths"]
        if (
            not isinstance(lengths, list)
            or not 1 <= len(lengths) <= settings.max_pages
            or any(type(length) is not int or length < 8 for length in lengths)
            or sum(lengths) != len(payload)
        ):
            raise ValueError
        images, offset = [], 0
        for length in lengths:
            image = payload[offset : offset + length]
            if (
                len(image) < 33
                or not image.startswith(b"\x89PNG\r\n\x1a\n")
                or image[12:16] != b"IHDR"
            ):
                raise ValueError
            width, height = struct.unpack(">II", image[16:24])
            if min(width, height) < 1 or max(width, height) > 10_000 or width * height > 25_000_000:
                raise ValueError
            images.append(image)
            offset += length
        return images
    except DocumentError:
        raise
    except (ValueError, KeyError, TypeError, UnicodeError, RecursionError):
        raise DocumentError("PARSER_FAILED") from None


def parse(data: bytes, operation: str, **metadata):
    if not data or len(data) > settings.max_file_bytes:
        raise DocumentError("FILE_SIZE_LIMIT")
    if not _slot.acquire(timeout=0.25):
        raise DocumentError("PARSER_BUSY")
    try:
        command = [
            sys.executable,
            "-I",
            "-B",
            str(_child),
            str(settings.parser_cpu_seconds),
            str(settings.parser_memory_mb),
            str(settings.max_file_bytes),
            str(settings.max_pages),
            str(settings.parser_max_output_bytes),
        ]
        request = json.dumps({"operation": operation, **metadata}).encode() + b"\n" + data
        with TemporaryFile() as output:
            try:
                with subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
                    close_fds=True,
                ) as child:
                    try:
                        child.communicate(request, timeout=settings.parser_timeout_seconds)
                    except subprocess.TimeoutExpired:
                        raise DocumentError("PARSER_TIMEOUT") from None
                    finally:
                        if child.poll() is None:
                            child.kill()
                            child.communicate()
                    if child.returncode:
                        code = (
                            "PARSER_RESOURCE_LIMIT"
                            if child.returncode in {-signal.SIGXCPU, -signal.SIGXFSZ}
                            else "PARSER_FAILED"
                        )
                        raise DocumentError(code)
            except OSError:
                raise DocumentError("PARSER_FAILED") from None
            output.seek(0)
            response = output.read(settings.parser_max_output_bytes + HEADER_LIMIT + 1)
        if len(response) > settings.parser_max_output_bytes + HEADER_LIMIT:
            raise DocumentError("PARSER_OUTPUT_LIMIT")
        return _decode(response, operation)
    finally:
        _slot.release()
