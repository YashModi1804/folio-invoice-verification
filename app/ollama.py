"""Local-only vision extraction; never falls back to a hosted provider."""

import base64
import json

import httpx
from pydantic import ValidationError

from app.config import settings
from app.domain.models import Invoice
from app.gemini import PROMPT, output_schema
from app.providers import Extraction, ProviderError


class OllamaProvider:
    def extract(self, pages: list[bytes], sample: str | None = None) -> Extraction:
        model = settings.ollama_model
        if not model or "cloud" in model.lower() or "/" in model:
            raise ProviderError("INVALID_LOCAL_MODEL_CONFIGURATION")
        schema = output_schema()
        body = {
            "model": model,
            "stream": False,
            "think": False,
            "keep_alive": "5m",
            "messages": [
                {"role": "system", "content": PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Extract this invoice from the ordered page images. "
                        "Use confidence numbers between 0 and 1, never percentages. "
                        "Dates are YYYY-MM-DD or null. Absent fields have value null, "
                        "confidence 0 and evidence []. Return only JSON matching this schema: "
                        + json.dumps(schema)
                    ),
                    "images": [base64.b64encode(page).decode() for page in pages],
                },
            ],
            "format": schema,
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 4096},
        }
        try:
            # Ignore proxy environment variables: documents must stay on loopback.
            with httpx.Client(timeout=settings.ollama_timeout_seconds, trust_env=False) as client:
                response = client.post("http://127.0.0.1:11434/api/chat", json=body)
        except httpx.TimeoutException as exc:
            raise ProviderError("LOCAL_MODEL_TIMEOUT") from exc
        except httpx.TransportError as exc:
            raise ProviderError("LOCAL_MODEL_UNAVAILABLE") from exc
        if response.status_code == 404:
            raise ProviderError("LOCAL_MODEL_NOT_INSTALLED")
        if response.status_code != 200:
            raise ProviderError("LOCAL_MODEL_REQUEST_FAILED")
        try:
            payload = response.json()
            if payload.get("done") is not True or payload.get("done_reason") != "stop":
                raise ProviderError("PROVIDER_INCOMPLETE_OUTPUT")
            invoice = Invoice.model_validate_json(payload["message"]["content"])
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise ProviderError("PROVIDER_INVALID_SCHEMA") from exc
        return Extraction(
            invoice,
            "ollama",
            model,
            {
                "input_tokens": payload.get("prompt_eval_count"),
                "output_tokens": payload.get("eval_count"),
                "estimated_cost_usd": "0",
                "pricing_version": "local-no-api-fee-v1",
                "cost_note": "No API fee. Hardware and electricity costs are excluded.",
            },
        )
