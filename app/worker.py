"""Database-backed worker. Run separately with python -m app.worker."""
import logging
import time
from datetime import timedelta

from sqlalchemy import select, update

from app.config import settings
from app.db import AuditEvent, Job, Session, now
from app.domain.routing import route
from app.domain.verify import verify
from app.gemini import PROMPT_VERSION, GeminiProvider
from app.providers import FixtureProvider, ProviderError
from app.storage import DocumentError, document_path, render

logger = logging.getLogger("folio.worker")


def run_once() -> bool:
    with Session.begin() as db:
        # A crashed/abandoned attempt is visible, not silently replayed and recharged.
        stale = now() - timedelta(minutes=10)
        abandoned = db.scalars(select(Job).where(Job.status == "PROCESSING",
                                                  Job.started_at < stale)).all()
        for job in abandoned:
            job.status, job.error, job.completed_at = "FAILED", "WORKER_INTERRUPTED", now()
            db.add(AuditEvent(job_id=job.id, event="FAILED", actor="worker",
                              details={"code": "WORKER_INTERRUPTED"}))
        job_id = db.scalar(select(Job.id).where(Job.status == "QUEUED")
                           .order_by(Job.created_at).limit(1))
        if job_id is None:
            return False
        claimed = db.execute(update(Job).where(Job.id == job_id, Job.status == "QUEUED")
                             .values(status="PROCESSING", started_at=now()))
        if claimed.rowcount != 1:
            return True
        db.add(AuditEvent(job_id=job_id, event="PROCESSING", actor="worker"))
    start = time.monotonic()
    try:
        with Session() as db:
            job = db.get(Job, job_id)
            pages = render(document_path(job_id).read_bytes(), job.media_type)
            provider = FixtureProvider() if job.sample or settings.provider == "fixture" \
                else GeminiProvider()
            extraction = provider.extract(pages, job.sample)
            checks = verify(extraction.invoice)
            status, reasons = route(extraction.invoice, checks,
                                    settings.confidence_threshold, job.page_count)
            result = {
                "invoice": extraction.invoice.model_dump(mode="json"),
                "checks": [c.model_dump(mode="json") for c in checks],
                "route_reasons": reasons,
                "math_validated": all(c.state == "PASS" for c in checks),
                "telemetry": {**extraction.usage, "provider": extraction.provider,
                              "model": extraction.model, "schema_version": "1",
                              "prompt_version": PROMPT_VERSION,
                              "latency_ms": round((time.monotonic() - start) * 1000)},
            }
        with Session.begin() as db:
            changed = db.execute(update(Job).where(Job.id == job_id, Job.status == "PROCESSING")
                                 .values(status=status, result=result, completed_at=now()))
            if changed.rowcount:
                db.add(AuditEvent(job_id=job_id, event=status, actor="policy-v1",
                                  details={"route_reasons": reasons}))
        logger.info("job_completed", extra={"job_id": job_id, "status": status})
    except Exception as exc:
        code = str(exc) if isinstance(exc, (ProviderError, DocumentError)) else "PROCESSING_FAILED"
        with Session.begin() as db:
            job = db.get(Job, job_id)
            job.status, job.error, job.completed_at = "FAILED", code, now()
            db.add(AuditEvent(job_id=job_id, event="FAILED", actor="worker", details={"code": code}))
        logger.error("job_failed", extra={"job_id": job_id, "code": code})
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        if not run_once():
            time.sleep(0.75)


if __name__ == "__main__":
    main()
