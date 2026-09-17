import json

import httpx
import pytest

from app.config import settings
from app.ollama import OllamaProvider
from app.providers import ProviderError
from app.samples import sample_invoice


def test_local_request_and_usage(monkeypatch):
    monkeypatch.setattr(settings, "ollama_model", "qwen3-vl:4b")

    def post(self, url, **kwargs):
        assert url == "http://127.0.0.1:11434/api/chat"
        body = kwargs["json"]
        assert body["messages"][1]["images"] == ["cGFnZQ=="]
        assert body["stream"] is False
        assert body["format"]["type"] == "object"
        assert "authorization" not in self.headers
        return httpx.Response(
            200,
            json={
                "done": True,
                "done_reason": "stop",
                "message": {"content": sample_invoice("clean").model_dump_json()},
                "prompt_eval_count": 100,
                "eval_count": 50,
            },
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    result = OllamaProvider().extract([b"page"])
    assert result.provider == "ollama"
    assert result.usage["input_tokens"] == 100
    assert result.usage["estimated_cost_usd"] == "0"


@pytest.mark.parametrize(
    "status,code", [(404, "LOCAL_MODEL_NOT_INSTALLED"), (500, "LOCAL_MODEL_REQUEST_FAILED")]
)
def test_safe_http_failure(monkeypatch, status, code):
    monkeypatch.setattr(httpx.Client, "post", lambda *a, **kw: httpx.Response(status))
    with pytest.raises(ProviderError, match=code):
        OllamaProvider().extract([b"page"])


@pytest.mark.parametrize("content", ["{}", "broken", json.dumps({"total_amount": "NaN"})])
def test_invalid_output_fails_closed(monkeypatch, content):
    monkeypatch.setattr(
        httpx.Client,
        "post",
        lambda *a, **kw: httpx.Response(
            200, json={"done": True, "done_reason": "stop", "message": {"content": content}}
        ),
    )
    with pytest.raises(ProviderError, match="PROVIDER_INVALID_SCHEMA"):
        OllamaProvider().extract([b"page"])


def test_truncated_output_rejected(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "post",
        lambda *a, **kw: httpx.Response(200, json={"done": True, "done_reason": "length"}),
    )
    with pytest.raises(ProviderError, match="PROVIDER_INCOMPLETE_OUTPUT"):
        OllamaProvider().extract([b"page"])


@pytest.mark.parametrize(
    "error,code",
    [(httpx.ReadTimeout, "LOCAL_MODEL_TIMEOUT"), (httpx.ConnectError, "LOCAL_MODEL_UNAVAILABLE")],
)
def test_transport_failure_not_retried(monkeypatch, error, code):
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        raise error("private diagnostic")

    monkeypatch.setattr(httpx.Client, "post", post)
    with pytest.raises(ProviderError, match=code):
        OllamaProvider().extract([b"page"])
    assert len(calls) == 1


def test_cloud_model_not_allowed(monkeypatch):
    monkeypatch.setattr(settings, "ollama_model", "qwen3-vl:235b-cloud")
    with pytest.raises(ProviderError, match="INVALID_LOCAL_MODEL_CONFIGURATION"):
        OllamaProvider().extract([b"page"])


def test_provider_is_pinned_at_upload(client, monkeypatch):
    from app import worker
    from app.providers import Extraction
    from app.samples import sample_pdf

    monkeypatch.setattr(settings, "provider", "ollama")
    monkeypatch.setattr(
        OllamaProvider,
        "extract",
        lambda *a, **kw: Extraction(sample_invoice("clean"), "ollama", "test-local"),
    )
    created = client.post(
        "/api/v1/documents",
        headers={"Idempotency-Key": "local-pinned"},
        files={"file": ("invoice.pdf", sample_pdf("clean"), "application/pdf")},
    ).json()
    monkeypatch.setattr(settings, "provider", "gemini")
    worker.run_once()
    result = client.get(f"/api/v1/jobs/{created['job_id']}").json()
    assert result["status"] == "AUTO_APPROVED"
    assert result["mode"] == "ollama"
    assert result["result"]["telemetry"]["provider"] == "ollama"
