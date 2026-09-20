"""Database-backed reservation of an intentionally conservative provider token budget."""

from datetime import datetime, timedelta

from sqlalchemy import select

from app.db import AuditEvent

RESERVATION_EVENT = "PROVIDER_CAPACITY_RESERVED"


def reserve_or_defer(db, *, estimated_tokens: int, limit: int, now: datetime) -> datetime | None:
    """Reserve capacity or return the earliest safe retry time without calling a provider."""
    cutoff = now - timedelta(minutes=1)
    reservations = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.event == RESERVATION_EVENT, AuditEvent.created_at > cutoff)
            .order_by(AuditEvent.created_at)
        )
    )
    used = sum(int(event.details.get("estimated_tokens", 0)) for event in reservations)
    if used + estimated_tokens <= limit:
        return None
    if not reservations:
        return now + timedelta(seconds=60)
    return reservations[0].created_at + timedelta(minutes=1)
