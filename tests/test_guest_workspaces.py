from datetime import timedelta

from app import api, retention, worker
from app.config import settings
from app.db import DocumentSource, GuestUploadUsage, Job, now
from app.samples import sample_pdf
from app.storage import document_path


def guest(client):
    response = client.post("/api/v1/guest-sessions")
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_guest_creation_is_opt_in(client):
    assert client.post("/api/v1/guest-sessions").status_code == 404


def test_guests_cannot_read_each_other_or_operator_records(client, monkeypatch):
    monkeypatch.setattr(settings, "guest_enabled", True)
    operator_job = client.post("/api/v1/samples/clean").json()["job_id"]
    first, second = guest(client), guest(client)
    owned_job = client.post("/api/v1/samples/helixpoint", headers=first).json()["job_id"]
    assert worker.run_once()
    assert worker.run_once()

    first_jobs = client.get("/api/v1/jobs", headers=first).json()
    second_jobs = client.get("/api/v1/jobs", headers=second).json()
    assert len(first_jobs) == 5
    assert len(second_jobs) == 4
    assert owned_job in {job["job_id"] for job in first_jobs}
    assert owned_job not in {job["job_id"] for job in second_jobs}
    assert all(job["mode"] == "fixture" for job in second_jobs)
    assert [item["job_id"] for item in client.get("/api/v1/jobs").json()] == [operator_job]
    for path in (
        f"/jobs/{owned_job}",
        f"/jobs/{owned_job}/pages/1",
        f"/jobs/{owned_job}/audit",
        f"/jobs/{owned_job}/decision",
        f"/jobs/{owned_job}/erp-export",
    ):
        assert client.get(f"/api/v1{path}", headers=second).status_code == 404
        assert client.get(f"/api/v1{path}").status_code == 404
    assert (
        client.post(
            f"/api/v1/review-tasks/{owned_job}/decision",
            headers=second,
            json={"action": "reject", "note": "Not my invoice"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/jobs/{owned_job}/erp-export/acknowledgements",
            headers=second,
            json={"system": "Demo", "external_record_id": "TEST-1"},
        ).status_code
        == 404
    )
    assert client.get(f"/api/v1/jobs/{operator_job}", headers=first).status_code == 404
    assert owned_job not in {
        item["job_id"] for item in client.get("/api/v1/review-tasks", headers=second).json()
    }
    assert client.get("/api/v1/metrics", headers=second).json()["total"] == 4
    owned = client.get(f"/api/v1/jobs/{owned_job}", headers=first).json()
    assert owned["status"] == "REQUIRES_HUMAN_REVIEW"
    assert len(owned["result"]["invoice"]["line_items"]) == 18
    assert owned["result"]["checks"][-1]["variance"] == "125.00"


def test_guest_upload_limits_do_not_count_samples(client, monkeypatch):
    monkeypatch.setattr(settings, "guest_enabled", True)
    monkeypatch.setattr(settings, "guest_uploads_per_guest_day", 1)
    monkeypatch.setattr(settings, "guest_uploads_per_day", 1)
    first, second = guest(client), guest(client)
    assert client.post("/api/v1/samples/clean", headers=first).status_code == 202
    document = sample_pdf("clean")

    def upload(headers, key):
        return client.post(
            "/api/v1/documents",
            files={"file": ("invoice.pdf", document)},
            headers={**headers, "Idempotency-Key": key},
        )

    assert upload(first, "one").status_code == 202
    assert upload(first, "one").status_code == 202
    assert upload(first, "two").status_code == 429
    assert upload(second, "one").status_code == 429


def test_idempotency_keys_are_private_to_each_guest(client, monkeypatch):
    monkeypatch.setattr(settings, "guest_enabled", True)
    document = sample_pdf("clean")
    first, second = guest(client), guest(client)

    def upload(headers):
        return client.post(
            "/api/v1/documents",
            files={"file": ("invoice.pdf", document)},
            headers={**headers, "Idempotency-Key": "same-browser-key"},
        )

    first_job = upload(first)
    second_job = upload(second)
    assert first_job.status_code == second_job.status_code == 202
    assert first_job.json()["job_id"] != second_job.json()["job_id"]


def test_guest_file_and_page_limits(client, monkeypatch):
    monkeypatch.setattr(settings, "guest_enabled", True)
    monkeypatch.setattr(settings, "guest_max_file_bytes", 100)
    headers = guest(client)
    response = client.post(
        "/api/v1/documents",
        files={"file": ("invoice.pdf", sample_pdf("clean"))},
        headers={**headers, "Idempotency-Key": "large"},
    )
    assert response.status_code == 413
    monkeypatch.setattr(settings, "guest_max_file_bytes", 5 * 1024 * 1024)
    monkeypatch.setattr(settings, "guest_max_pages", 1)
    response = client.post(
        "/api/v1/documents",
        files={"file": ("invoice.pdf", sample_pdf("clean"))},
        headers={**headers, "Idempotency-Key": "pages"},
    )
    assert response.status_code == 422


def test_guest_access_and_samples_survive_upload_expiry(client, monkeypatch):
    monkeypatch.setattr(settings, "guest_enabled", True)
    headers = guest(client)
    sample_id = client.get("/api/v1/jobs", headers=headers).json()[0]["job_id"]
    uploaded = client.post(
        "/api/v1/documents",
        files={"file": ("private.pdf", sample_pdf("clean"))},
        headers={**headers, "Idempotency-Key": "old-upload"},
    )
    assert uploaded.status_code == 202
    job_id = uploaded.json()["job_id"]
    assert document_path(job_id).exists()
    with api.Session.begin() as db:
        db.get(Job, job_id).created_at = now() - timedelta(hours=2, seconds=1)
        db.get(Job, sample_id).created_at = now() - timedelta(days=30)
    assert client.get(f"/api/v1/jobs/{job_id}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/jobs/{job_id}/pages/1", headers=headers).status_code == 404
    assert client.get(f"/api/v1/jobs/{job_id}/audit", headers=headers).status_code == 404
    assert client.get(f"/api/v1/jobs/{job_id}/decision", headers=headers).status_code == 404
    assert client.get(f"/api/v1/jobs/{job_id}/erp-export", headers=headers).status_code == 404
    assert client.get("/api/v1/metrics", headers=headers).json()["total"] == 4
    assert len(client.get("/api/v1/jobs", headers=headers).json()) == 4
    assert client.get(f"/api/v1/jobs/{sample_id}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/jobs/{sample_id}/pages/1", headers=headers).status_code == 200
    assert retention.expire_guest_uploads() == 1
    assert not document_path(job_id).exists()
    with api.Session() as db:
        assert db.get(Job, job_id) is None
        assert db.query(GuestUploadUsage).count() == 1
    assert client.get("/api/v1/jobs", headers=headers).status_code == 200


def test_guest_upload_bytes_are_removed_from_database(client, monkeypatch):
    monkeypatch.setattr(settings, "guest_enabled", True)
    monkeypatch.setattr(settings, "source_storage", "database")
    headers = guest(client)
    uploaded = client.post(
        "/api/v1/documents",
        files={"file": ("private.pdf", sample_pdf("clean"))},
        headers={**headers, "Idempotency-Key": "db-upload"},
    )
    assert uploaded.status_code == 202
    job_id = uploaded.json()["job_id"]
    with api.Session.begin() as db:
        assert db.get(DocumentSource, job_id) is not None
        db.get(Job, job_id).created_at = now() - timedelta(hours=2, seconds=1)
    assert retention.expire_guest_uploads() == 1
    with api.Session() as db:
        assert db.get(DocumentSource, job_id) is None
        assert db.get(Job, job_id) is None


def test_deleted_upload_still_counts_toward_rolling_daily_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "guest_enabled", True)
    monkeypatch.setattr(settings, "guest_uploads_per_guest_day", 1)
    headers = guest(client)
    first = client.post(
        "/api/v1/documents",
        files={"file": ("private.pdf", sample_pdf("clean"))},
        headers={**headers, "Idempotency-Key": "first"},
    )
    assert first.status_code == 202
    with api.Session.begin() as db:
        db.get(Job, first.json()["job_id"]).created_at = now() - timedelta(hours=3)
    assert retention.expire_guest_uploads() == 1
    second = client.post(
        "/api/v1/documents",
        files={"file": ("another.pdf", sample_pdf("clean"))},
        headers={**headers, "Idempotency-Key": "second"},
    )
    assert second.status_code == 429
    with api.Session.begin() as db:
        db.query(GuestUploadUsage).update(
            {GuestUploadUsage.created_at: now() - timedelta(days=1, seconds=1)}
        )
    assert retention.expire_guest_uploads() == 0
    assert (
        client.post(
            "/api/v1/documents",
            files={"file": ("another.pdf", sample_pdf("clean"))},
            headers={**headers, "Idempotency-Key": "second"},
        ).status_code
        == 202
    )


def test_expired_queued_guest_work_is_not_processed(client, monkeypatch):
    monkeypatch.setattr(settings, "guest_enabled", True)
    headers = guest(client)
    job_id = client.post(
        "/api/v1/documents",
        files={"file": ("private.pdf", sample_pdf("clean"))},
        headers={**headers, "Idempotency-Key": "queued-old"},
    ).json()["job_id"]
    with api.Session.begin() as db:
        db.get(Job, job_id).created_at = now() - timedelta(hours=2, seconds=1)
    assert worker.run_once() is False
    assert retention.expire_guest_uploads() == 1
    with api.Session() as db:
        assert db.get(Job, job_id) is None
