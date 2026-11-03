from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from sqlalchemy import func, select

from app import api
from app.config import settings
from app.db import GuestSession, GuestUploadUsage, Job, now
from app.samples import sample_pdf


def test_guest_creation_is_bounded_and_existing_access_keeps_working(client, monkeypatch):
    monkeypatch.setattr(settings, "guest_enabled", True)
    monkeypatch.setattr(settings, "guest_sessions_per_hour", 1)
    first = client.post("/api/v1/guest-sessions")
    assert first.status_code == 201
    headers = {"Authorization": f"Bearer {first.json()['token']}"}
    rejected = client.post("/api/v1/guest-sessions")
    assert rejected.status_code == 429
    assert 1 <= int(rejected.headers["retry-after"]) <= 3600
    assert rejected.headers["cache-control"] == "no-store"
    assert len(client.get("/api/v1/jobs", headers=headers).json()) == 4
    with api.Session() as db:
        assert db.scalar(select(func.count()).select_from(GuestSession)) == 1
        assert db.scalar(select(func.count()).select_from(Job)) == 4


def test_guest_admission_has_rolling_day_and_total_bounds(client, monkeypatch):
    monkeypatch.setattr(settings, "guest_enabled", True)
    monkeypatch.setattr(settings, "guest_sessions_per_day", 1)
    monkeypatch.setattr(settings, "guest_workspace_limit", 1)
    assert client.post("/api/v1/guest-sessions").status_code == 201
    with api.Session.begin() as db:
        db.scalar(select(GuestSession)).created_at = now() - timedelta(hours=2)
    daily = client.post("/api/v1/guest-sessions")
    assert daily.status_code == 429
    assert int(daily.headers["retry-after"]) > 3600
    with api.Session.begin() as db:
        db.scalar(select(GuestSession)).created_at = now() - timedelta(days=2)
    full = client.post("/api/v1/guest-sessions")
    assert full.status_code == 429
    assert "capacity" in full.json()["detail"]
    monkeypatch.setattr(settings, "guest_workspace_limit", 2)
    assert client.post("/api/v1/guest-sessions").status_code == 201


def test_concurrent_guest_creation_does_not_oversubscribe(client, monkeypatch):
    monkeypatch.setattr(settings, "guest_enabled", True)
    monkeypatch.setattr(settings, "guest_sessions_per_hour", 2)
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(lambda _: client.post("/api/v1/guest-sessions"), range(4)))
    assert sorted(response.status_code for response in responses) == [201, 201, 429, 429]
    with api.Session() as db:
        assert db.scalar(select(func.count()).select_from(GuestSession)) == 2
        assert db.scalar(select(func.count()).select_from(Job)) == 8


def test_concurrent_guest_retries_do_not_spend_the_allowance_twice(client, monkeypatch):
    monkeypatch.setattr(settings, "guest_enabled", True)
    monkeypatch.setattr(settings, "guest_uploads_per_guest_day", 1)
    token = client.post("/api/v1/guest-sessions").json()["token"]
    document = sample_pdf("clean")

    def upload(key):
        return client.post(
            "/api/v1/documents",
            files={"file": ("invoice.pdf", document)},
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(upload, ["same-upload", "same-upload"]))
    assert [response.status_code for response in responses] == [202, 202]
    assert responses[0].json()["job_id"] == responses[1].json()["job_id"]
    assert upload("second-upload").status_code == 429
    with api.Session() as db:
        assert db.scalar(select(func.count()).select_from(GuestUploadUsage)) == 1


def test_exhausted_guest_allowance_is_rejected_before_native_parsing(client, monkeypatch):
    monkeypatch.setattr(settings, "guest_enabled", True)
    token = client.post("/api/v1/guest-sessions").json()["token"]
    with api.Session.begin() as db:
        guest = db.scalar(select(GuestSession))
        for _ in range(settings.guest_uploads_per_guest_day):
            db.add(GuestUploadUsage(guest_id=guest.id))

    def unexpected_parse(*args):
        raise AssertionError("Exhausted guests must not reach the parser")

    monkeypatch.setattr(api, "inspect", unexpected_parse)
    response = client.post(
        "/api/v1/documents",
        files={"file": ("invoice.pdf", b"%PDF-not-parsed")},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "over-limit"},
    )
    assert response.status_code == 429
