import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from starlette.exceptions import HTTPException

from app import integrations, review  # noqa: F401 — registers integration and review routes
from app.api import router
from app.config import settings
from app.db import Job, Session, WorkerHeartbeat, engine, now


@asynccontextmanager
async def lifespan(_app):
    if settings.public_demo:
        token = settings.operator_token.get_secret_value()
        if token == "local-demo-only" or len(token) < 32:
            raise RuntimeError(
                "Public demo requires a unique operator token of at least 32 characters"
            )
        if settings.provider == "groq" and not settings.groq_api_key.get_secret_value():
            raise RuntimeError("Public Groq demo requires GROQ_API_KEY")
        if settings.provider == "gemini" and not settings.gemini_api_key.get_secret_value():
            raise RuntimeError("Public Gemini demo requires GEMINI_API_KEY")
    if settings.embedded_worker:
        from app.worker import main as run_worker

        threading.Thread(target=run_worker, daemon=True, name="folio-worker").start()
    yield


app = FastAPI(title="Folio · Document verification", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_context(request: Request, call_next):
    correlation_id = str(uuid4())
    request.state.correlation_id = correlation_id
    # Bound multipart requests before the framework buffers them on disk.
    length = request.headers.get("content-length")
    if request.method == "POST" and request.url.path == "/api/v1/documents" and not length:
        return JSONResponse(
            {"detail": "Content-Length required", "correlation_id": correlation_id}, status_code=411
        )
    if length and (not length.isdigit() or int(length) > settings.max_file_bytes + 65536):
        return JSONResponse(
            {"detail": "FILE_SIZE_LIMIT", "correlation_id": correlation_id}, status_code=413
        )
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "correlation_id": request.state.correlation_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Invalid request fields",
            "fields": [".".join(str(v) for v in e["loc"]) for e in exc.errors()],
            "correlation_id": request.state.correlation_id,
        },
    )


@app.get("/health/live")
def liveness():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM processing_jobs LIMIT 1"))
        with Session() as db:
            heartbeat = db.scalar(
                select(WorkerHeartbeat.id)
                .where(WorkerHeartbeat.last_seen > now() - timedelta(minutes=3))
                .limit(1)
            )
        storage_ok = settings.source_storage == "database" or (
            settings.storage_dir.is_dir() and os.access(settings.storage_dir, os.W_OK)
        )
        body = {
            "database": "ready",
            "worker": "ready" if heartbeat else "unavailable",
            "storage": "ready" if storage_ok else "unavailable",
        }
        return JSONResponse(body, status_code=200 if heartbeat and storage_ok else 503)
    except Exception:
        return JSONResponse({"database": "unavailable"}, status_code=503)


@router.get("/metrics")
def metrics():
    with Session() as db:
        jobs = db.scalars(select(Job)).all()
        counts = {}
        for job in jobs:
            counts[job.status] = counts.get(job.status, 0) + 1
        latencies = sorted(j.result["telemetry"]["latency_ms"] for j in jobs if j.result)
        completed = [j for j in jobs if j.status not in {"QUEUED", "PROCESSING"}]
        denominator = len(completed) or 1
        extracted = [j for j in jobs if j.result]
        return {
            "total": len(jobs),
            "counts": counts,
            "failure_rate": counts.get("FAILED", 0) / denominator,
            "review_rate": sum(bool(j.result["route_reasons"]) for j in extracted)
            / (len(extracted) or 1),
            "verification_failure_rate": sum(j.result["math_validated"] is False for j in extracted)
            / (len(extracted) or 1),
            "cost_note": "Per-document estimates are in job telemetry; unknown costs are null.",
            "p50_ms": latencies[len(latencies) // 2] if latencies else None,
            "p95_ms": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))]
            if latencies
            else None,
            "as_of": time.time(),
        }


# Router must be included after all decorators have registered.
app.include_router(router)
frontend = Path("web/dist")
if frontend.exists():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="console")
