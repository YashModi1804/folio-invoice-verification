from datetime import timedelta

import pymupdf
import pytest
from sqlalchemy import select

from app import api, retention, worker
from app.db import Job, now
from app.domain.routing import route
from app.domain.verify import verify
from app.samples import sample_invoice, sample_pdf
from app.storage import DocumentError, document_path, inspect


def test_encrypted_pdf_is_rejected():
    with pymupdf.open(stream=sample_pdf("clean"), filetype="pdf") as doc:
        data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="test-password")
    with pytest.raises(DocumentError, match="PASSWORD_PROTECTED_PDF"):
        inspect(data, "private.pdf")


def test_page_limit():
    with pymupdf.open() as doc:
        for _ in range(21):
            doc.new_page()
        data = doc.tobytes()
    with pytest.raises(DocumentError, match="PAGE_LIMIT"):
        inspect(data, "long.pdf")


def test_content_type_must_match_extension():
    with pytest.raises(DocumentError, match="CONTENT_TYPE_MISMATCH"):
        inspect(sample_pdf("clean"), "fake.png")


def test_interrupted_live_attempt_is_not_replayed(client):
    job_id = client.post("/api/v1/samples/clean").json()["job_id"]
    with api.Session.begin() as db:
        job = db.get(Job, job_id)
        job.status = "PROCESSING"
        job.started_at = now() - timedelta(minutes=15)
    assert not worker.run_once()
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "FAILED"
    assert job["error"] == "WORKER_INTERRUPTED"


def test_retention_dry_run_then_source_expiration(client):
    job_id = client.post("/api/v1/samples/clean").json()["job_id"]
    worker.run_once()
    with api.Session.begin() as db:
        db.get(Job, job_id).created_at = now() - timedelta(days=10)
    assert retention.expire_sources() == [job_id]
    assert document_path(job_id).exists()
    retention.expire_sources(apply=True)
    assert not document_path(job_id).exists()
    assert client.get(f"/api/v1/jobs/{job_id}").json()["result"] is not None
    assert client.get(f"/api/v1/jobs/{job_id}/pages/1").status_code == 410


def test_error_payload_excludes_submitted_private_values(client):
    job_id = client.post("/api/v1/samples/uncertain").json()["job_id"]
    worker.run_once()
    response = client.post(
        f"/api/v1/review-tasks/{job_id}/decision",
        json={"action": "PRIVATE-SOURCE-TEXT", "note": "abc"},
    )
    assert response.status_code == 422
    assert "PRIVATE-SOURCE-TEXT" not in response.text
    assert "correlation_id" in response.json()


def test_processing_error_does_not_leak_provider_details(client, monkeypatch):
    job_id = client.post("/api/v1/samples/clean").json()["job_id"]

    def crash(*args, **kwargs):
        raise RuntimeError("sensitive document content")

    monkeypatch.setattr(worker.FixtureProvider, "extract", crash)
    worker.run_once()
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["error"] == "PROCESSING_FAILED"
    assert "sensitive document content" not in str(job)


def test_whitespace_review_note_is_invalid(client):
    job_id = client.post("/api/v1/samples/uncertain").json()["job_id"]
    worker.run_once()
    assert (
        client.post(
            f"/api/v1/review-tasks/{job_id}/decision", json={"action": "approve", "note": "   "}
        ).status_code
        == 422
    )


def test_negative_tax_amount_is_reviewed():
    invoice = sample_invoice("clean")
    invoice.tax_amount.value = -1
    status, reasons = route(invoice, verify(invoice))
    assert status == "REQUIRES_HUMAN_REVIEW"
    assert "NEGATIVE_AMOUNT_REQUIRES_REVIEW" in reasons


def test_negative_printed_discount_is_a_discount_magnitude():
    invoice = sample_invoice("clean")
    invoice.discount_amount.value = -50
    invoice.total_amount.value = 1200
    checks = verify(invoice)
    assert checks[-1].state == "PASS"
    assert "NEGATIVE_AMOUNT_REQUIRES_REVIEW" not in route(invoice, checks)[1]


def test_timestamps_are_explicit_utc(client):
    job = client.post("/api/v1/samples/clean").json()
    assert job["created_at"].endswith("+00:00")


def test_idempotency_leaves_only_one_stored_record(client):
    data = sample_pdf("clean")
    for _ in range(3):
        client.post(
            "/api/v1/documents",
            files={"file": ("sample.pdf", data)},
            headers={"Idempotency-Key": "same"},
        )
    with api.Session() as db:
        assert len(db.scalars(select(Job)).all()) == 1
