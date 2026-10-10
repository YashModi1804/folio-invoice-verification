"""Apply source retention and remove temporary guest uploads."""

import argparse
from datetime import timedelta

from sqlalchemy import delete, select

from app.config import settings
from app.db import AuditEvent, GuestUploadUsage, Job, ReviewDecision, Session, now
from app.storage import delete_source, source_exists


def expire_sources(apply: bool = False) -> list[str]:
    cutoff = now() - timedelta(days=settings.retention_days)
    expired = []
    with Session.begin() as db:
        jobs = db.scalars(
            select(Job).where(Job.created_at < cutoff, Job.status.notin_(["QUEUED", "PROCESSING"]))
        )
        for job in jobs:
            if not source_exists(db, job.id):
                continue
            expired.append(job.id)
            if apply:
                delete_source(db, job.id)
                db.add(
                    AuditEvent(
                        job_id=job.id,
                        event="SOURCE_EXPIRED",
                        actor="retention",
                        details={"retention_days": settings.retention_days},
                    )
                )
    return expired


def expire_guest_uploads() -> int:
    """Remove guest uploads and their private history after access has ended."""
    removed = 0
    cutoff = now() - timedelta(minutes=settings.guest_upload_retention_minutes)
    with Session.begin() as db:
        jobs = db.scalars(
            select(Job).where(
                Job.workspace_id != "operator",
                Job.sample.is_(None),
                Job.created_at <= cutoff,
            )
        ).all()
        for job in jobs:
            if job.status == "PROCESSING":
                continue
            delete_source(db, job.id)
            db.execute(delete(AuditEvent).where(AuditEvent.job_id == job.id))
            db.execute(delete(ReviewDecision).where(ReviewDecision.job_id == job.id))
            db.delete(job)
            removed += 1
        db.execute(
            delete(GuestUploadUsage).where(GuestUploadUsage.created_at < now() - timedelta(days=1))
        )
    return removed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Permanently remove expired sources")
    args = parser.parse_args()
    ids = expire_sources(args.apply)
    print(f"{'Deleted' if args.apply else 'Would delete'} {len(ids)} expired source files.")
