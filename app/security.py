"""Request bounds and consistent response protections at the ASGI boundary."""

import logging
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings

logger = logging.getLogger("folio.http")


class RequestGuard:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = str(uuid4())
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        path = scope["path"]
        headers = Headers(scope=scope)
        upload = scope["method"] == "POST" and path.rstrip("/") == "/api/v1/documents"
        limit = settings.max_file_bytes + 65536 if upload else settings.max_request_body_bytes
        response_started = False
        received = 0

        async def protected_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Correlation-ID"] = correlation_id
                response_headers["X-Content-Type-Options"] = "nosniff"
                response_headers["Referrer-Policy"] = "no-referrer"
                response_headers["X-Frame-Options"] = "DENY"
                response_headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                if scope["scheme"] == "https" or headers.get("x-forwarded-proto") == "https":
                    response_headers["Strict-Transport-Security"] = "max-age=31536000"
                if not path.startswith(("/docs", "/redoc", "/openapi.json")):
                    response_headers["Content-Security-Policy"] = (
                        "default-src 'self'; base-uri 'self'; object-src 'none'; "
                        "frame-ancestors 'none'; script-src 'self'; "
                        "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                        "font-src 'self'; connect-src 'self'; form-action 'self'"
                    )
                if path.startswith("/api/"):
                    response_headers["Cache-Control"] = "no-store"
            await send(message)

        async def reject(status: int, detail: str) -> None:
            response = JSONResponse(
                {"detail": detail, "correlation_id": correlation_id}, status_code=status
            )
            await response(scope, receive, protected_send)

        lengths = headers.getlist("content-length")
        if len(lengths) > 1 or (
            lengths
            and (not lengths[0].isascii() or not lengths[0].isdigit() or len(lengths[0]) > 20)
        ):
            await reject(400, "Invalid Content-Length")
            return
        if upload and not lengths:
            await reject(411, "Content-Length required")
            return
        if lengths and int(lengths[0]) > limit:
            await reject(413, "FILE_SIZE_LIMIT" if upload else "REQUEST_BODY_LIMIT")
            return

        async def bounded_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(413, "FILE_SIZE_LIMIT" if upload else "REQUEST_BODY_LIMIT")
            return message

        try:
            await self.app(scope, bounded_receive, protected_send)
        except Exception:
            if response_started:
                raise
            # Exception text can contain database credentials or document content.
            logger.error("request_failed", extra={"correlation_id": correlation_id})
            await reject(500, "Internal server error")
