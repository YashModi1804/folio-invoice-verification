import time
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from app import review  # noqa: F401 — registers review routes
from app.api import router
from app.db import Job, Session, engine

app = FastAPI(title="Folio · Document verification", version="0.1.0")
app.include_router(router)


@app.middleware("http")
async def request_context(request: Request, call_next):
    correlation_id = str(uuid4())
    request.state.correlation_id = correlation_id
    # Bound multipart requests before the framework buffers them on disk.
    from app.config import settings
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > settings.max_file_bytes + 65536):
        return JSONResponse({"detail": "FILE_SIZE_LIMIT", "correlation_id": correlation_id},
                            status_code=413)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422, content={"detail": "Invalid request fields",
        "fields": [".".join(str(v) for v in e["loc"]) for e in exc.errors()],
        "correlation_id": request.state.correlation_id})


@app.get("/health/live")
def liveness():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM processing_jobs LIMIT 1"))
        return {"database": "ready", "worker": "separate-process; see queue age"}
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
        return {"total": len(jobs), "counts": counts,
                "p50_ms": latencies[len(latencies) // 2] if latencies else None,
                "p95_ms": latencies[min(len(latencies) - 1, int(len(latencies) * .95))]
                if latencies else None, "as_of": time.time()}


# Router must be included after all decorators have registered.
app.include_router(router, include_in_schema=False)
frontend = Path("web/dist")
if frontend.exists():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="console")
