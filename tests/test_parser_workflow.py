import pytest

from app import api, worker
from app.db import Job, now
from app.samples import sample_pdf
from app.storage import DocumentError


@pytest.mark.parametrize("code,status", [("PARSER_BUSY", 503), ("PARSER_TIMEOUT", 422)])
def test_upload_and_preview_expose_safe_parser_errors(client, monkeypatch, code, status):
    job = client.post("/api/v1/samples/clean").json()

    def fail(*args, **kwargs):
        raise DocumentError(code)

    monkeypatch.setattr(api, "inspect", fail)
    upload = client.post(
        "/api/v1/documents",
        files={"file": ("invoice.pdf", sample_pdf("clean"))},
        headers={"Idempotency-Key": "parser-rejection"},
    )
    monkeypatch.setattr(api, "render", fail)
    preview = client.get(f"/api/v1/jobs/{job['job_id']}/pages/1")
    for response in (upload, preview):
        assert response.status_code == status
        assert response.json()["detail"] == code
        assert response.headers["x-content-type-options"] == "nosniff"
        if code == "PARSER_BUSY":
            assert response.headers["retry-after"] == "2"


def test_busy_parser_requeues_before_provider_and_later_completes(client, monkeypatch):
    job_id = client.post("/api/v1/samples/clean").json()["job_id"]
    render = worker.render

    def busy(*args, **kwargs):
        raise DocumentError("PARSER_BUSY")

    monkeypatch.setattr(worker, "render", busy)
    assert worker.run_once()
    waiting = client.get(f"/api/v1/jobs/{job_id}").json()
    assert waiting["status"] == "QUEUED"
    assert waiting["not_before"] is not None
    assert waiting["result"] is None
    monkeypatch.setattr(worker, "render", render)
    with api.Session.begin() as db:
        db.get(Job, job_id).not_before = now()
    assert worker.run_once()
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "AUTO_APPROVED"
