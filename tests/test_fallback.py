import pytest

from app import worker
from app.config import settings
from app.gemini import GeminiProvider
from app.groq import GroqProvider
from app.ollama import OllamaProvider
from app.providers import Extraction, ProviderError
from app.samples import sample_invoice, sample_pdf


def enqueue(client, monkeypatch, enabled=True):
    monkeypatch.setattr(settings, "provider", "gemini")
    monkeypatch.setattr(settings, "local_fallback_enabled", enabled)
    response = client.post(
        "/api/v1/documents",
        files={"file": ("invoice.pdf", sample_pdf("clean"), "application/pdf")},
        headers={"Idempotency-Key": "fallback-test"},
    )
    assert response.status_code == 202
    return response.json()["job_id"]


def fail(code):
    def extract(*args, **kwargs):
        raise ProviderError(code)

    return extract


@pytest.mark.parametrize("code", sorted(worker.FALLBACK_ERRORS))
def test_availability_fallback_is_audited_and_not_relabelled(client, monkeypatch, code):
    job_id = enqueue(client, monkeypatch)
    # Consent belongs to the job, not the current workspace settings.
    monkeypatch.setattr(settings, "local_fallback_enabled", False)
    monkeypatch.setattr(GeminiProvider, "extract", fail(code))
    calls = []

    def local(*args, **kwargs):
        calls.append(1)
        return Extraction(sample_invoice("clean"), "ollama", "test-local")

    monkeypatch.setattr(OllamaProvider, "extract", local)
    worker.run_once()
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "AUTO_APPROVED"
    assert job["mode"] == "ollama"
    assert job["requested_provider"] == "gemini"
    assert job["result"]["telemetry"]["fallback_reason"] == code
    assert job["result"]["telemetry"]["estimated_cost_usd"] is None
    audit = client.get(f"/api/v1/jobs/{job_id}/audit").json()
    assert [a["event"] for a in audit] == [
        "UPLOADED",
        "PROCESSING",
        "LOCAL_FALLBACK_STARTED",
        "AUTO_APPROVED",
    ]
    assert calls == [1]


@pytest.mark.parametrize(
    "code,enabled",
    [
        ("PROVIDER_RATE_LIMITED", False),
        ("PROVIDER_INVALID_SCHEMA", True),
        ("PROVIDER_INCOMPLETE_OUTPUT", True),
        ("PROVIDER_REQUEST_REJECTED", True),
    ],
)
def test_fallback_does_not_hide_bad_output_or_bypass_consent(client, monkeypatch, code, enabled):
    job_id = enqueue(client, monkeypatch, enabled)
    monkeypatch.setattr(settings, "local_fallback_enabled", True)
    monkeypatch.setattr(GeminiProvider, "extract", fail(code))
    monkeypatch.setattr(OllamaProvider, "extract", lambda *a: pytest.fail("Unexpected local call"))
    worker.run_once()
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "FAILED"
    assert job["error"] == code


def test_math_failure_is_reviewed_without_reextracting(client, monkeypatch):
    job_id = enqueue(client, monkeypatch)
    monkeypatch.setattr(
        GeminiProvider,
        "extract",
        lambda *a: Extraction(sample_invoice("variance"), "gemini", "test-cloud"),
    )
    monkeypatch.setattr(OllamaProvider, "extract", lambda *a: pytest.fail("Unexpected local call"))
    worker.run_once()
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "REQUIRES_HUMAN_REVIEW"
    assert job["mode"] == "gemini"


def test_both_failures_remain_visible(client, monkeypatch):
    job_id = enqueue(client, monkeypatch)
    monkeypatch.setattr(GeminiProvider, "extract", fail("PROVIDER_RATE_LIMITED"))
    monkeypatch.setattr(OllamaProvider, "extract", fail("LOCAL_MODEL_UNAVAILABLE"))
    worker.run_once()
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "FAILED"
    assert job["error"] == "LOCAL_MODEL_UNAVAILABLE"
    audit = client.get(f"/api/v1/jobs/{job_id}/audit").json()
    assert audit[-2]["details"]["code"] == "PROVIDER_RATE_LIMITED"


def test_groq_fallback_retains_cloud_identity_and_safe_quota_details(client, monkeypatch):
    monkeypatch.setattr(settings, "provider", "groq")
    monkeypatch.setattr(settings, "local_fallback_enabled", True)
    job = client.post(
        "/api/v1/documents",
        files={"file": ("test.pdf", sample_pdf("clean"))},
        headers={"Idempotency-Key": "groq-fallback"},
    ).json()

    def unavailable(*args):
        raise ProviderError("PROVIDER_RATE_LIMITED", details={"reset_tokens": "45s"})

    monkeypatch.setattr(GroqProvider, "extract", unavailable)
    monkeypatch.setattr(
        OllamaProvider,
        "extract",
        lambda *a: Extraction(sample_invoice("clean"), "ollama", "test-local"),
    )
    worker.run_once()
    saved = client.get(f"/api/v1/jobs/{job['job_id']}").json()
    assert saved["status"] == "AUTO_APPROVED"
    assert saved["result"]["telemetry"]["requested_provider"] == "groq"
    audit = client.get(f"/api/v1/jobs/{job['job_id']}/audit").json()
    assert audit[-2]["details"]["reset_tokens"] == "45s"
    assert audit[-2]["details"]["note"].startswith("Groq unavailable")
