from fastapi import HTTPException
from sqlalchemy import select, update

from app.api import CurrentAccess, get_job, router, serialize, visible_jobs
from app.db import AuditEvent, Job, ReviewDecision, Session, timestamp
from app.domain.models import Decision, Invoice
from app.domain.verify import verify


@router.get("/review-tasks")
def review_tasks(access: CurrentAccess):
    with Session() as db:
        jobs = db.scalars(
            select(Job)
            .where(Job.status == "REQUIRES_HUMAN_REVIEW", *visible_jobs(access))
            .order_by(Job.created_at)
        ).all()
        return sorted(
            [serialize(j) for j in jobs],
            key=lambda j: -sum(c["state"] == "FAIL" for c in j["result"]["checks"]),
        )


@router.post("/review-tasks/{job_id}/decision")
def decide(job_id: str, decision: Decision, access: CurrentAccess):
    with Session.begin() as db:
        job = get_job(db, job_id, access)
        if job.status != "REQUIRES_HUMAN_REVIEW":
            raise HTTPException(409, "This review is already resolved or unavailable")
        original = Invoice.model_validate(job.result["invoice"])
        corrected = decision.corrected_invoice or original
        checks = verify(corrected)
        # Explicit human acceptance is permitted even if the source invoice itself is wrong.
        # Preserve remaining warnings and the required note in the decision record.
        status = "HUMAN_APPROVED" if decision.action == "approve" else "REJECTED"
        changed = db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == "REQUIRES_HUMAN_REVIEW")
            .values(status=status)
        )
        if changed.rowcount != 1:
            raise HTTPException(409, "Another reviewer already resolved this task")
        before, after = original.model_dump(mode="json"), corrected.model_dump(mode="json")
        changes = {
            key: {"before": before[key], "after": after[key]}
            for key in before
            if before[key] != after[key]
        }
        db.add(
            ReviewDecision(
                job_id=job_id,
                actor=access.actor,
                action=decision.action,
                note=decision.note,
                corrected_invoice=after,
                checks=[c.model_dump(mode="json") for c in checks],
            )
        )
        db.add(
            AuditEvent(
                job_id=job_id,
                event=status,
                actor=access.actor,
                details={"changes": changes, "note": decision.note, "source_extraction_version": 1},
            )
        )
        return {"status": status, "correlation_id": job.correlation_id}


@router.get("/jobs/{job_id}/audit")
def audit(job_id: str, access: CurrentAccess):
    with Session() as db:
        get_job(db, job_id, access)
        return [
            {
                "event": e.event,
                "actor": e.actor,
                "details": e.details,
                "created_at": timestamp(e.created_at),
            }
            for e in db.scalars(
                select(AuditEvent)
                .where(AuditEvent.job_id == job_id)
                .order_by(AuditEvent.created_at)
            )
        ]


@router.get("/jobs/{job_id}/decision")
def decision_detail(job_id: str, access: CurrentAccess):
    with Session() as db:
        get_job(db, job_id, access)
        item = db.scalar(select(ReviewDecision).where(ReviewDecision.job_id == job_id))
        if item is None:
            return None
        return {
            "action": item.action,
            "actor": item.actor,
            "note": item.note,
            "invoice": item.corrected_invoice,
            "checks": item.checks,
            "created_at": timestamp(item.created_at),
        }
