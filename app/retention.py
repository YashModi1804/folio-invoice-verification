"""Delete expired source files only. Dry-run by default; records and audit remain."""

import argparse
from datetime import timedelta

from sqlalchemy import select

from app.config import settings
from app.db import AuditEvent, Job, Session, now
from app.storage import document_path


def expire_sources(apply: bool = False) -> list[str]:
    cutoff = now() - timedelta(days=settings.retention_days)
    expired = []
    with Session.begin() as db:
        jobs = db.scalars(
            select(Job).where(Job.created_at < cutoff, Job.status.notin_(["QUEUED", "PROCESSING"]))
        )
        for job in jobs:
            path = document_path(job.id)
            if not path.exists():
                continue
            expired.append(job.id)
            if apply:
                path.unlink()
                db.add(
                    AuditEvent(
                        job_id=job.id,
                        event="SOURCE_EXPIRED",
                        actor="retention",
                        details={"retention_days": settings.retention_days},
                    )
                )
    return expired


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Permanently remove expired sources")
    args = parser.parse_args()
    ids = expire_sources(args.apply)
    print(f"{'Deleted' if args.apply else 'Would delete'} {len(ids)} expired source files.")
