import hashlib
import secrets
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.db import AuditEvent, Job, Session, timestamp
from app.samples import SAMPLES, sample_pdf
from app.storage import DocumentError, document_path, inspect, render

bearer = HTTPBearer(auto_error=False)


def authenticate(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    if not credentials or not secrets.compare_digest(
        credentials.credentials, settings.operator_token.get_secret_value()
    ):
        raise HTTPException(401, "Authentication required")
    return settings.operator_name


router = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticate)])


def get_job(db, job_id):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Document not found")
    return job


def serialize(job):
    effective = (
        job.review_decision.corrected_invoice
        if job.review_decision
        else (job.result["invoice"] if job.result else None)
    )
    return {
        "job_id": job.id,
        "document_id": job.id,
        "correlation_id": job.correlation_id,
        "filename": job.filename,
        "status": job.status,
        "page_count": job.page_count,
        "created_at": timestamp(job.created_at),
        "not_before": timestamp(job.not_before) if job.not_before else None,
        "error": job.error,
        "mode": job.result["telemetry"]["provider"] if job.result else job.provider,
        "requested_provider": job.provider,
        "result": job.result,
        "summary": {
            key: effective[key]["value"]
            for key in ("vendor_name", "invoice_number", "total_amount", "currency")
        }
        if effective
        else None,
    }


def enqueue(data: bytes, filename: str, key: str, sample: str | None = None):
    if not 1 <= len(key) <= 128:
        raise HTTPException(422, "Idempotency key must contain 1–128 characters")
    checksum = hashlib.sha256(data).hexdigest()
    with Session() as db:
        existing = db.scalar(select(Job).where(Job.idempotency_key == key))
        if existing:
            if existing.checksum != checksum or existing.sample != sample:
                raise HTTPException(409, "Idempotency key already used for another document")
            return serialize(existing)
    try:
        media_type, pages = inspect(data, filename)
    except DocumentError as exc:
        raise HTTPException(422, str(exc)) from exc
    job_id = str(uuid4())
    path = document_path(job_id)
    path.write_bytes(data)
    path.chmod(0o600)
    try:
        with Session.begin() as db:
            job = Job(
                id=job_id,
                idempotency_key=key,
                checksum=checksum,
                filename=Path(filename).name[:255],
                media_type=media_type,
                page_count=pages,
                sample=sample,
                provider="fixture" if sample else settings.provider,
            )
            db.add(job)
            db.flush()
            db.add(
                AuditEvent(
                    job_id=job.id,
                    event="UPLOADED",
                    actor=settings.operator_name,
                    details={
                        "mode": "fixture" if sample else settings.provider,
                        "local_fallback_enabled": bool(
                            not sample
                            and settings.provider in {"gemini", "groq"}
                            and settings.local_fallback_enabled
                        ),
                    },
                )
            )
            result = serialize(job)
        return result
    except IntegrityError:
        path.unlink(missing_ok=True)
        with Session() as db:
            existing = db.scalar(select(Job).where(Job.idempotency_key == key))
            if existing and existing.checksum == checksum and existing.sample == sample:
                return serialize(existing)
        raise HTTPException(409, "Conflicting concurrent upload") from None
    except Exception:
        path.unlink(missing_ok=True)
        raise


@router.get("/config")
def configuration():
    return {
        "provider": settings.provider,
        "local_fallback_enabled": settings.local_fallback_enabled,
        "max_file_mb": settings.max_file_bytes // 1024**2,
        "max_pages": settings.max_pages,
        "samples": [
            {"id": key, "name": value[0], "description": value[1]} for key, value in SAMPLES.items()
        ],
    }


@router.post("/documents", status_code=202)
async def upload(
    file: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str, Header()],
):
    data = await file.read(settings.max_file_bytes + 1)
    await file.close()
    return await run_in_threadpool(enqueue, data, file.filename or "upload", idempotency_key)


@router.post("/samples/{kind}", status_code=202)
def upload_sample(kind: str):
    if kind not in SAMPLES:
        raise HTTPException(404, "Sample not found")
    return enqueue(sample_pdf(kind), f"northline-{kind}.pdf", str(uuid4()), kind)


@router.get("/jobs")
def list_jobs():
    with Session() as db:
        return [
            serialize(job)
            for job in db.scalars(select(Job).order_by(Job.created_at.desc()).limit(100))
        ]


@router.get("/jobs/{job_id}")
def job_detail(job_id: str):
    with Session() as db:
        return serialize(get_job(db, job_id))


@router.get("/jobs/{job_id}/pages/{page_number}")
def page_image(job_id: str, page_number: int):
    with Session() as db:
        job = get_job(db, job_id)
        if not 1 <= page_number <= job.page_count:
            raise HTTPException(404, "Page not found")
        path = document_path(job.id)
        if not path.exists():
            raise HTTPException(410, "Source document retention period ended")
        pages = render(path.read_bytes(), job.media_type)
        return Response(
            pages[page_number - 1], media_type="image/png", headers={"Cache-Control": "no-store"}
        )
