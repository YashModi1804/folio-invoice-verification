import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, timedelta
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.db import AuditEvent, GuestSession, GuestUploadUsage, Job, Session, now, timestamp
from app.domain.routing import route
from app.domain.verify import verify
from app.samples import SAMPLES, sample_invoice, sample_pdf
from app.storage import DocumentError, document_path, inspect, read_source, render, save_source

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Access:
    workspace_id: str
    actor: str
    guest: bool = False


def authenticate(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Access:
    if not credentials:
        raise HTTPException(401, "Authentication required")
    if secrets.compare_digest(credentials.credentials, settings.operator_token.get_secret_value()):
        return Access("operator", settings.operator_name)
    if settings.guest_enabled:
        token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
        with Session() as db:
            guest = db.scalar(select(GuestSession).where(GuestSession.token_hash == token_hash))
            if guest:
                return Access(guest.id, "Guest reviewer", guest=True)
    raise HTTPException(401, "Authentication required")


CurrentAccess = Annotated[Access, Depends(authenticate)]
router = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticate)])
guest_router = APIRouter(prefix="/api/v1")


def seed_guest_samples(db, workspace_id: str) -> None:
    """Create private, preverified fixture copies without inference calls."""
    for kind in SAMPLES:
        invoice = sample_invoice(kind)
        checks = verify(invoice)
        status, reasons = route(invoice, checks, page_count=2)
        source = sample_pdf(kind)
        job = Job(
            workspace_id=workspace_id,
            idempotency_key=hashlib.sha256(f"{workspace_id}:sample:{kind}".encode()).hexdigest(),
            checksum=hashlib.sha256(source).hexdigest(),
            filename=f"{kind}-sample.pdf",
            media_type="application/pdf",
            page_count=2,
            sample=kind,
            provider="fixture",
            status=status,
            result={
                "invoice": invoice.model_dump(mode="json"),
                "checks": [check.model_dump(mode="json") for check in checks],
                "route_reasons": reasons,
                "math_validated": all(check.state == "PASS" for check in checks),
                "telemetry": {
                    "provider": "fixture",
                    "model": "synthetic-v1",
                    "input_tokens": None,
                    "output_tokens": None,
                    "estimated_cost_usd": "0",
                    "pricing_version": "fixture-no-api",
                    "latency_ms": 0,
                    "prompt_version": "fixture-v1",
                    "schema_version": "1",
                },
            },
            completed_at=now(),
        )
        db.add(job)
        db.flush()
        # Fixture PDFs are reproducible assets; avoid duplicating them for every visitor.
        db.add(
            AuditEvent(
                job_id=job.id,
                event="SAMPLE_LOADED",
                actor="fixture",
                details={"mode": "fixture", "kind": kind},
            )
        )


@guest_router.post("/guest-sessions", status_code=201)
def create_guest_session():
    if not settings.guest_enabled:
        raise HTTPException(404, "Guest access is unavailable")
    token = secrets.token_urlsafe(48)
    with Session.begin() as db:
        guest = GuestSession(token_hash=hashlib.sha256(token.encode()).hexdigest())
        db.add(guest)
        db.flush()
        seed_guest_samples(db, guest.id)
        return {"token": token}


def visible_jobs(access: Access):
    query = Job.workspace_id == access.workspace_id
    if access.guest:
        cutoff = now() - timedelta(minutes=settings.guest_upload_retention_minutes)
        return (query, or_(Job.sample.is_not(None), Job.created_at > cutoff))
    return (query,)


def get_job(db, job_id, access: Access):
    job = db.get(Job, job_id)
    if job is None or job.workspace_id != access.workspace_id:
        raise HTTPException(404, "Document not found")
    if access.guest and job.sample is None:
        created = job.created_at.replace(tzinfo=job.created_at.tzinfo or UTC)
        if created <= now() - timedelta(minutes=settings.guest_upload_retention_minutes):
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


def enqueue(data: bytes, filename: str, key: str, access: Access, sample: str | None = None):
    if not 1 <= len(key) <= 128:
        raise HTTPException(422, "Idempotency key must contain 1–128 characters")
    if access.guest and not sample and len(data) > settings.guest_max_file_bytes:
        raise HTTPException(413, "Guest upload size limit exceeded")
    scoped_key = (
        hashlib.sha256(f"{access.workspace_id}:{key}".encode()).hexdigest() if access.guest else key
    )
    checksum = hashlib.sha256(data).hexdigest()
    with Session() as db:
        existing = db.scalar(select(Job).where(Job.idempotency_key == scoped_key))
        if existing:
            get_job(db, existing.id, access)
            if existing.checksum != checksum or existing.sample != sample:
                raise HTTPException(409, "Idempotency key already used for another document")
            return serialize(existing)
    try:
        media_type, pages = inspect(data, filename)
    except DocumentError as exc:
        raise HTTPException(422, str(exc)) from exc
    if access.guest and pages > settings.guest_max_pages:
        raise HTTPException(422, "Guest page limit exceeded")
    job_id = str(uuid4())
    try:
        with Session.begin() as db:
            if access.guest and not sample:
                if db.bind.dialect.name == "postgresql":
                    db.execute(text("SELECT pg_advisory_xact_lock(188734091)"))
                day_ago = now() - timedelta(days=1)
                daily = db.scalar(
                    select(func.count())
                    .select_from(GuestUploadUsage)
                    .where(GuestUploadUsage.created_at >= day_ago)
                )
                guest_daily = db.scalar(
                    select(func.count())
                    .select_from(GuestUploadUsage)
                    .where(
                        GuestUploadUsage.guest_id == access.workspace_id,
                        GuestUploadUsage.created_at >= day_ago,
                    )
                )
                pending = db.scalar(
                    select(func.count())
                    .select_from(Job)
                    .where(
                        Job.workspace_id != "operator",
                        Job.sample.is_(None),
                        Job.status.in_(("QUEUED", "PROCESSING")),
                        Job.created_at
                        > now() - timedelta(minutes=settings.guest_upload_retention_minutes),
                    )
                )
                if daily >= settings.guest_uploads_per_day or pending >= settings.guest_queue_limit:
                    raise HTTPException(429, "Live demo capacity reached; try again later")
                if guest_daily >= settings.guest_uploads_per_guest_day:
                    raise HTTPException(429, "Guest daily upload allowance reached")
                db.add(GuestUploadUsage(guest_id=access.workspace_id))
            if access.guest and sample:
                sample_count = db.scalar(
                    select(func.count())
                    .select_from(Job)
                    .where(Job.workspace_id == access.workspace_id, Job.sample.is_not(None))
                )
                if sample_count >= 8:
                    raise HTTPException(429, "Guest sample allowance ended")
            job = Job(
                id=job_id,
                workspace_id=access.workspace_id,
                idempotency_key=scoped_key,
                checksum=checksum,
                filename=Path(filename).name[:255],
                media_type=media_type,
                page_count=pages,
                sample=sample,
                provider="fixture" if sample else settings.provider,
            )
            db.add(job)
            db.flush()
            save_source(db, job_id, data)
            db.add(
                AuditEvent(
                    job_id=job.id,
                    event="UPLOADED",
                    actor=access.actor,
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
        if settings.source_storage == "file":
            document_path(job_id).unlink(missing_ok=True)
        with Session() as db:
            existing = db.scalar(select(Job).where(Job.idempotency_key == scoped_key))
            if existing and existing.checksum == checksum and existing.sample == sample:
                get_job(db, existing.id, access)
                return serialize(existing)
        raise HTTPException(409, "Conflicting concurrent upload") from None
    except Exception:
        if settings.source_storage == "file":
            document_path(job_id).unlink(missing_ok=True)
        raise


@router.get("/config")
def configuration(access: CurrentAccess):
    return {
        "workspace": "guest" if access.guest else "operator",
        "guest_upload_retention_minutes": settings.guest_upload_retention_minutes
        if access.guest
        else None,
        "provider": settings.provider,
        "local_fallback_enabled": settings.local_fallback_enabled,
        "max_file_mb": (settings.guest_max_file_bytes if access.guest else settings.max_file_bytes)
        // 1024**2,
        "max_pages": settings.guest_max_pages if access.guest else settings.max_pages,
        "temporary_demo": settings.public_demo,
        "samples": [
            {"id": key, "name": value[0], "description": value[1]} for key, value in SAMPLES.items()
        ],
    }


@router.post("/documents", status_code=202)
async def upload(
    file: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str, Header()],
    access: CurrentAccess,
):
    limit = settings.guest_max_file_bytes if access.guest else settings.max_file_bytes
    data = await file.read(limit + 1)
    await file.close()
    return await run_in_threadpool(
        enqueue, data, file.filename or "upload", idempotency_key, access
    )


@router.post("/samples/{kind}", status_code=202)
def upload_sample(kind: str, access: CurrentAccess):
    if kind not in SAMPLES:
        raise HTTPException(404, "Sample not found")
    return enqueue(sample_pdf(kind), f"{kind}-sample.pdf", str(uuid4()), access, kind)


@router.get("/jobs")
def list_jobs(access: CurrentAccess):
    with Session() as db:
        return [
            serialize(job)
            for job in db.scalars(
                select(Job).where(*visible_jobs(access)).order_by(Job.created_at.desc()).limit(100)
            )
        ]


@router.get("/jobs/{job_id}")
def job_detail(job_id: str, access: CurrentAccess):
    with Session() as db:
        return serialize(get_job(db, job_id, access))


@router.get("/jobs/{job_id}/pages/{page_number}")
def page_image(job_id: str, page_number: int, access: CurrentAccess):
    with Session() as db:
        job = get_job(db, job_id, access)
        if not 1 <= page_number <= job.page_count:
            raise HTTPException(404, "Page not found")
        source = read_source(db, job.id)
        if source is None and access.guest and job.sample:
            source = sample_pdf(job.sample)
        if source is None:
            raise HTTPException(410, "Source document retention period ended")
        pages = render(source, job.media_type, page_numbers=(page_number,))
        return Response(pages[0], media_type="image/png", headers={"Cache-Control": "no-store"})
