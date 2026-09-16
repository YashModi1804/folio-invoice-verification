import httpx
import pytest
from pydantic import SecretStr

from app.config import settings
from app.gemini import GeminiProvider
from app.providers import ProviderError
from app.samples import sample_invoice


@pytest.fixture
def live_settings(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr("test-key"))
    monkeypatch.setattr(settings, "gemini_model", "test-vision-model")
    monkeypatch.setattr("app.gemini.time.sleep", lambda _: None)


def reply(text, finish="STOP"):
    return {"candidates": [{"finishReason": finish, "content": {"parts": [{"text": text}]}}],
            "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 80}}


def test_schema_and_usage_are_preserved(monkeypatch, live_settings):
    def post(self, url, **kwargs):
        assert kwargs["headers"]["x-goog-api-key"] == "test-key"
        assert "responseJsonSchema" in kwargs["json"]["generationConfig"]
        assert "systemInstruction" in kwargs["json"]
        return httpx.Response(200, json=reply(sample_invoice("clean").model_dump_json()))
    monkeypatch.setattr(httpx.Client, "post", post)
    result = GeminiProvider().extract([b"synthetic-image"])
    assert result.usage["input_tokens"] == 120
    assert result.usage["estimated_cost_usd"] is None
    assert result.invoice.vendor_name.value == "Northline Studio"


@pytest.mark.parametrize("payload,code", [
    (reply("{}"), "PROVIDER_INVALID_SCHEMA"),
    (reply("{broken"), "PROVIDER_INVALID_SCHEMA"),
    ({"candidates": []}, "PROVIDER_INVALID_SCHEMA"),
    (reply("{}", "MAX_TOKENS"), "PROVIDER_INCOMPLETE_OUTPUT"),
])
def test_bad_model_outputs_are_safe(monkeypatch, live_settings, payload, code):
    monkeypatch.setattr(httpx.Client, "post", lambda *a, **kw: httpx.Response(200, json=payload))
    with pytest.raises(ProviderError, match=code):
        GeminiProvider().extract([b"image"])


def test_rate_limit_retries_are_bounded(monkeypatch, live_settings):
    calls = []
    def post(*args, **kwargs):
        calls.append(1)
        return httpx.Response(429)
    monkeypatch.setattr(httpx.Client, "post", post)
    with pytest.raises(ProviderError, match="PROVIDER_UNAVAILABLE"):
        GeminiProvider().extract([b"image"])
    assert len(calls) == 3


def test_transport_timeout_is_not_blindly_replayed(monkeypatch, live_settings):
    calls = []
    def post(*args, **kwargs):
        calls.append(1)
        raise httpx.ReadTimeout("sensitive upstream text")
    monkeypatch.setattr(httpx.Client, "post", post)
    with pytest.raises(ProviderError, match="PROVIDER_TRANSPORT_FAILURE"):
        GeminiProvider().extract([b"image"])
    assert len(calls) == 1
