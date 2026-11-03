"""Bound anonymous workspace creation without expiring existing credentials."""

import math
from datetime import UTC, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select, text

from app.config import settings
from app.db import GuestSession, GuestUploadUsage, Job, now


def lock_guest_mutation(db) -> None:
    """Serialize count-and-insert quotas for both supported databases."""
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(188734091)"))
    elif db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))


def admit_guest_session(db) -> None:
    lock_guest_mutation(db)
    instant = now()
    for window, limit in (
        (timedelta(hours=1), settings.guest_sessions_per_hour),
        (timedelta(days=1), settings.guest_sessions_per_day),
    ):
        count, oldest = db.execute(
            select(func.count(), func.min(GuestSession.created_at)).where(
                GuestSession.created_at > instant - window
            )
        ).one()
        if count >= limit:
            reset = oldest.replace(tzinfo=oldest.tzinfo or UTC) + window
            retry_after = max(1, math.ceil((reset - instant).total_seconds()))
            raise HTTPException(
                429,
                "The guest demo is busy. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )
    total = db.scalar(select(func.count()).select_from(GuestSession))
    if total >= settings.guest_workspace_limit:
        raise HTTPException(
            429, "Guest workspace capacity reached. Existing guests can still return."
        )


def check_guest_allowance(db, workspace_id: str, *, sample: bool) -> None:
    """Reject exhausted allowances before parsing; recheck under the admission lock."""
    if sample:
        count = db.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.workspace_id == workspace_id, Job.sample.is_not(None))
        )
        if count >= 8:
            raise HTTPException(429, "Guest sample allowance ended")
        return
    day_ago = now() - timedelta(days=1)
    daily = db.scalar(
        select(func.count())
        .select_from(GuestUploadUsage)
        .where(GuestUploadUsage.created_at >= day_ago)
    )
    guest_daily = db.scalar(
        select(func.count())
        .select_from(GuestUploadUsage)
        .where(GuestUploadUsage.guest_id == workspace_id, GuestUploadUsage.created_at >= day_ago)
    )
    pending = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(
            Job.workspace_id != "operator",
            Job.sample.is_(None),
            Job.status.in_(("QUEUED", "PROCESSING")),
            Job.created_at > now() - timedelta(minutes=settings.guest_upload_retention_minutes),
        )
    )
    if daily >= settings.guest_uploads_per_day or pending >= settings.guest_queue_limit:
        raise HTTPException(429, "Live demo capacity reached; try again later")
    if guest_daily >= settings.guest_uploads_per_guest_day:
        raise HTTPException(429, "Guest daily upload allowance reached")
