import json

import httpx
import pytest
from pydantic import SecretStr

from app.config import settings
from app.groq import GroqProvider
from app.providers import ProviderError
from app.samples import sample_invoice, sample_pdf


@pytest.fixture(autouse=True)
def groq_settings(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", SecretStr("test-groq-key"))
    monkeypatch.setattr(settings, "groq_model", "qwen/qwen3.8-27b")


def reply(content=None, finish="stop"):
    return {
        "id": "request-test",
        "choices": [
            {
                "finish_reason": finish,
                "message": {
                    "content": content
                    if content is not None
                    else sample_invoice("clean").model_dump_json()
                },
            }
        ],
        "usage": {"prompt_tokens": 123, "completion_tokens": 456},
    }


def test_groq_contract_and_usage(monkeypatch):
    def post(self, url, **kwargs):
        assert url == "https://api.groq.com/openai/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer test-groq-key"
        body = json.loads(kwargs["content"])
        assert body["response_format"] == {"type": "json_object"}
        assert body["reasoning_effort"] == "none"
        assert body["max_completion_tokens"] == 4096
        assert len(body["messages"][1]["content"]) == 3
        assert body["messages"][1]["content"][1]["image_url"]["url"].startswith(
            "data:image/png;base64,"
        )
        return httpx.Response(200, json=reply())

    monkeypatch.setattr(httpx.Client, "post", post)
    result = GroqProvider().extract([b"page1", b"page2"])
    assert result.provider == "groq"
    assert result.usage["input_tokens"] == 123
    assert result.usage["provider_request_id"] == "request-test"
    assert result.usage["estimated_cost_usd"] is None


@pytest.mark.parametrize(
    "status,code",
    [
        (429, "PROVIDER_RATE_LIMITED"),
        (503, "PROVIDER_UNAVAILABLE"),
        (401, "PROVIDER_ACCESS_DENIED"),
        (403, "PROVIDER_ACCESS_DENIED"),
        (400, "PROVIDER_REQUEST_REJECTED"),
    ],
)
def test_groq_errors_are_safe_and_never_retried(monkeypatch, status, code):
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        return httpx.Response(status, text="private upstream response")

    monkeypatch.setattr(httpx.Client, "post", post)
    with pytest.raises(ProviderError, match=code):
        GroqProvider().extract([b"page"])
    assert calls == [1]


@pytest.mark.parametrize(
    "payload,code",
    [
        (reply("{}"), "PROVIDER_INVALID_SCHEMA"),
        (reply("broken"), "PROVIDER_INVALID_SCHEMA"),
        ({"choices": []}, "PROVIDER_INVALID_SCHEMA"),
        (reply(finish="length"), "PROVIDER_INCOMPLETE_OUTPUT"),
    ],
)
def test_groq_untrusted_output_is_validated(monkeypatch, payload, code):
    monkeypatch.setattr(httpx.Client, "post", lambda *a, **kw: httpx.Response(200, json=payload))
    with pytest.raises(ProviderError, match=code):
        GroqProvider().extract([b"page"])


def test_groq_limits_reject_before_any_network_call(monkeypatch):
    monkeypatch.setattr(httpx.Client, "post", lambda *a, **kw: pytest.fail("Unexpected request"))
    with pytest.raises(ProviderError, match="PROVIDER_PAGE_LIMIT_EXCEEDED"):
        GroqProvider().extract([b"page"] * 4)
    with pytest.raises(ProviderError, match="PROVIDER_PAYLOAD_TOO_LARGE"):
        GroqProvider().extract([b"x" * (16 * 1024 * 1024)])


def test_groq_timeout_is_not_retried(monkeypatch):
    def post(*args, **kwargs):
        raise httpx.ReadTimeout("private")

    monkeypatch.setattr(httpx.Client, "post", post)
    with pytest.raises(ProviderError, match="PROVIDER_READ_TIMEOUT"):
        GroqProvider().extract([b"page"])


def test_groq_worker_and_page_limit(client, monkeypatch):
    import pymupdf

    from app import worker
    from app.providers import Extraction

    monkeypatch.setattr(settings, "provider", "groq")
    monkeypatch.setattr(settings, "groq_tokens_per_minute", 20_000)
    assert client.get("/api/v1/config").json()["max_pages"] == 20
    monkeypatch.setattr(
        GroqProvider, "extract", lambda *a: Extraction(sample_invoice("clean"), "groq", "test")
    )
    job = client.post(
        "/api/v1/documents",
        files={"file": ("two.pdf", sample_pdf("clean"))},
        headers={"Idempotency-Key": "groq"},
    ).json()
    worker.run_once()
    saved = client.get(f"/api/v1/jobs/{job['job_id']}").json()
    assert saved["mode"] == "groq"
    assert saved["status"] == "AUTO_APPROVED"
    with pymupdf.open() as doc:
        for _ in range(4):
            doc.new_page()
        data = doc.tobytes()
    job = client.post(
        "/api/v1/documents",
        files={"file": ("four.pdf", data)},
        headers={"Idempotency-Key": "too-many"},
    ).json()
    assert worker.run_once()
    saved = client.get(f"/api/v1/jobs/{job['job_id']}").json()
    assert saved["status"] == "REQUIRES_HUMAN_REVIEW"
    assert "INCOMPLETE_PAGE_COVERAGE" in saved["result"]["route_reasons"]
    assert saved["result"]["checks"][-2]["state"] == "NOT_APPLICABLE"
    assert saved["result"]["telemetry"]["page_plan"]["selected_pages"] == [1, 2, 4]
    assert saved["result"]["telemetry"]["page_plan"]["skipped_pages"] == [3]


def test_groq_defers_a_job_before_provider_call_when_token_budget_is_reserved(client, monkeypatch):
    from app import worker
    from app.providers import Extraction

    monkeypatch.setattr(settings, "provider", "groq")
    monkeypatch.setattr(settings, "groq_tokens_per_minute", 6_696)
    monkeypatch.setattr(
        GroqProvider, "extract", lambda *a: Extraction(sample_invoice("clean"), "groq", "test")
    )
    first = client.post(
        "/api/v1/documents",
        files={"file": ("first.pdf", sample_pdf("clean"))},
        headers={"Idempotency-Key": "capacity-first"},
    ).json()
    second = client.post(
        "/api/v1/documents",
        files={"file": ("second.pdf", sample_pdf("clean"))},
        headers={"Idempotency-Key": "capacity-second"},
    ).json()
    assert worker.run_once()
    assert client.get(f"/api/v1/jobs/{first['job_id']}").json()["status"] == "AUTO_APPROVED"
    assert worker.run_once()
    deferred = client.get(f"/api/v1/jobs/{second['job_id']}").json()
    assert deferred["status"] == "QUEUED"
    assert deferred["not_before"] is not None
    audit = client.get(f"/api/v1/jobs/{second['job_id']}/audit").json()
    assert audit[-1]["event"] == "PROVIDER_CAPACITY_DEFERRED"
