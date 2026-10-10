"""Stable, vendor-neutral exports for ERP and accounting-system connectors."""

from fastapi import HTTPException
from sqlalchemy import select

from app.api import CurrentAccess, get_job, router
from app.db import AuditEvent, ReviewDecision, Session, timestamp
from app.domain.models import ERPExportAcknowledgement

APPROVED_STATUSES = {"AUTO_APPROVED", "HUMAN_APPROVED"}
EXPORT_SCHEMA_VERSION = "folio.erp-export.v1"


def approved_export(job, decision: ReviewDecision | None) -> dict:
    if job.status not in APPROVED_STATUSES:
        raise HTTPException(409, "Only approved records can be exported to an ERP")
    result = job.result or {}
    invoice = decision.corrected_invoice if decision else result["invoice"]
    checks = decision.checks if decision else result["checks"]

    def value(field: str):
        return invoice[field]["value"]

    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "event_type": "invoice.approved",
        "idempotency_key": f"folio:{job.id}:v1",
        "folio": {
            "job_id": job.id,
            "correlation_id": job.correlation_id,
            "status": job.status,
            "approved_at": timestamp(job.completed_at),
        },
        "invoice": {
            "supplier": {"name": value("vendor_name"), "tax_id": value("vendor_tax_id")},
            "invoice_number": value("invoice_number"),
            "invoice_date": value("invoice_date"),
            "currency": value("currency"),
            "amounts": {
                "subtotal": value("subtotal"),
                "tax": value("tax_amount"),
                "shipping": value("shipping_amount"),
                "discount": value("discount_amount"),
                "total": value("total_amount"),
            },
            "line_items": invoice["line_items"],
        },
        "verification": {
            "checks": checks,
            "math_validated": result.get("math_validated"),
            "reviewed_by": decision.actor if decision else None,
        },
    }


@router.get("/jobs/{job_id}/erp-export")
def erp_export(job_id: str, access: CurrentAccess):
    with Session() as db:
        job = get_job(db, job_id, access)
        decision = db.scalar(select(ReviewDecision).where(ReviewDecision.job_id == job_id))
        return approved_export(job, decision)


@router.post("/jobs/{job_id}/erp-export/acknowledgements")
def acknowledge_erp_export(
    job_id: str,
    acknowledgement: ERPExportAcknowledgement,
    access: CurrentAccess,
):
    with Session.begin() as db:
        job = get_job(db, job_id, access)
        decision = db.scalar(select(ReviewDecision).where(ReviewDecision.job_id == job_id))
        export = approved_export(job, decision)
        acknowledgements = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.job_id == job_id,
                    AuditEvent.event == "ERP_EXPORT_ACKNOWLEDGED",
                )
            )
        )
        details = acknowledgement.model_dump()
        if not any(event.details == details for event in acknowledgements):
            db.add(
                AuditEvent(
                    job_id=job_id,
                    event="ERP_EXPORT_ACKNOWLEDGED",
                    actor=access.actor,
                    details=details,
                )
            )
        return {
            "status": "acknowledged",
            "idempotency_key": export["idempotency_key"],
            "correlation_id": job.correlation_id,
        }
