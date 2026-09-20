import pytest

from app import worker
from app.samples import sample_pdf


def processed(client, kind):
    response = client.post(f"/api/v1/samples/{kind}")
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert worker.run_once()
    return client.get(f"/api/v1/jobs/{job_id}").json()


@pytest.mark.parametrize(
    "kind,status",
    [
        ("clean", "AUTO_APPROVED"),
        ("variance", "REQUIRES_HUMAN_REVIEW"),
        ("uncertain", "REQUIRES_HUMAN_REVIEW"),
    ],
)
def test_sample_routes(client, kind, status):
    job = processed(client, kind)
    assert job["status"] == status
    assert job["page_count"] == 2
    assert job["result"]["telemetry"]["provider"] == "fixture"
    assert (
        client.get(f"/api/v1/jobs/{job['job_id']}/pages/2").headers["content-type"] == "image/png"
    )


def test_review_preserves_original_and_prevents_duplicate_decision(client):
    job = processed(client, "variance")
    corrected = job["result"]["invoice"]
    corrected["total_amount"]["value"] = "1250.00"
    path = f"/api/v1/review-tasks/{job['job_id']}/decision"
    payload = {
        "action": "approve",
        "note": "Confirmed subtotal and corrected total",
        "corrected_invoice": corrected,
    }
    assert client.post(path, json=payload).status_code == 200
    assert client.post(path, json=payload).status_code == 409
    saved = client.get(f"/api/v1/jobs/{job['job_id']}").json()
    assert saved["status"] == "HUMAN_APPROVED"
    assert saved["summary"]["total_amount"] == "1250.00"
    assert saved["result"]["invoice"]["total_amount"]["value"] == "1300.00"
    audit = client.get(f"/api/v1/jobs/{job['job_id']}/audit").json()
    assert audit[-1]["details"]["changes"]["total_amount"]["after"]["value"] == "1250.00"
    assert client.get("/api/v1/review-tasks").json() == []


def test_erp_export_is_approved_only_and_idempotently_acknowledged(client):
    review = processed(client, "variance")
    assert client.get(f"/api/v1/jobs/{review['job_id']}/erp-export").status_code == 409
    corrected = review["result"]["invoice"]
    corrected["total_amount"]["value"] = "1250.00"
    assert (
        client.post(
            f"/api/v1/review-tasks/{review['job_id']}/decision",
            json={
                "action": "approve",
                "note": "Confirmed corrected amount for export",
                "corrected_invoice": corrected,
            },
        ).status_code
        == 200
    )
    export = client.get(f"/api/v1/jobs/{review['job_id']}/erp-export").json()
    assert export["schema_version"] == "folio.erp-export.v1"
    assert export["invoice"]["amounts"]["total"] == "1250.00"
    payload = {"system": "Odoo", "external_record_id": "BILL-401"}
    path = f"/api/v1/jobs/{review['job_id']}/erp-export/acknowledgements"
    assert client.post(path, json=payload).status_code == 200
    assert client.post(path, json=payload).status_code == 200
    audit = client.get(f"/api/v1/jobs/{review['job_id']}/audit").json()
    assert [item["event"] for item in audit].count("ERP_EXPORT_ACKNOWLEDGED") == 1


def test_idempotent_upload_and_conflict(client):
    data = sample_pdf("clean")

    def upload(content):
        return client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", content)},
            headers={"Idempotency-Key": "once"},
        )

    first = upload(data)
    assert first.status_code == 202
    assert upload(data).json()["job_id"] == first.json()["job_id"]
    assert upload(sample_pdf("variance")).status_code == 409
    worker.run_once()
    job = client.get(f"/api/v1/jobs/{first.json()['job_id']}").json()
    assert job["status"] == "FAILED"
    assert job["error"] == "LIVE_PROVIDER_NOT_CONFIGURED"


@pytest.mark.parametrize(
    "filename,data", [("bad.exe", b"bad"), ("bad.pdf", b"%PDF-bad"), ("bad.png", b"not an image")]
)
def test_unsupported_or_corrupt_files(client, filename, data):
    response = client.post(
        "/api/v1/documents", files={"file": (filename, data)}, headers={"Idempotency-Key": "bad"}
    )
    assert response.status_code == 422


def test_authentication_covers_documents_and_review(client):
    for path in ("/jobs", "/review-tasks", "/config", "/metrics"):
        assert (
            client.get(f"/api/v1{path}", headers={"Authorization": "Bearer wrong"}).status_code
            == 401
        )


def test_worker_does_not_reprocess_terminal_jobs(client):
    processed(client, "clean")
    assert not worker.run_once()


def test_reject_requires_note(client):
    job = processed(client, "uncertain")
    path = f"/api/v1/review-tasks/{job['job_id']}/decision"
    assert client.post(path, json={"action": "reject", "note": ""}).status_code == 422
    assert (
        client.post(path, json={"action": "reject", "note": "Unreadable date"}).status_code == 200
    )


def test_health_and_metrics(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 503
    worker.run_once()
    assert client.get("/health/ready").status_code == 200
    processed(client, "clean")
    assert client.get("/api/v1/metrics").json()["counts"]["AUTO_APPROVED"] == 1
