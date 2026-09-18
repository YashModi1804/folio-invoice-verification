"""Groq vision JSON mode, with strict local schema validation and no cloud replay."""

import base64
import json
import re

import httpx
from pydantic import ValidationError

from app.config import settings
from app.domain.models import Invoice
from app.gemini import PROMPT, output_schema
from app.providers import Extraction, ProviderError

GROQ_PROMPT_VERSION = "invoice-v1-groq-v1"
VISION_PAGE_LIMITS = {"qwen/qwen3.6-27b": 5, "qwen/qwen3.8-27b": 3}


class GroqProvider:
    def extract(self, pages: list[bytes], sample: str | None = None) -> Extraction:
        key = settings.groq_api_key.get_secret_value()
        if not key:
            raise ProviderError("LIVE_PROVIDER_NOT_CONFIGURED")
        limit = VISION_PAGE_LIMITS.get(settings.groq_model)
        if limit is None:
            raise ProviderError("INVALID_MODEL_CONFIGURATION")
        if not pages or len(pages) > limit:
            raise ProviderError("PROVIDER_PAGE_LIMIT_EXCEEDED")
        body = {
            "model": settings.groq_model,
            "stream": False,
            "reasoning_effort": "none",
            "temperature": 0,
            "max_completion_tokens": 4096,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract the invoice from these ordered pages. Return JSON "
                                "matching this schema exactly. Tax-inclusive means tax is "
                                "already included in subtotal or unit prices, not merely "
                                "present as a separate added amount. " + json.dumps(output_schema())
                            ),
                        },
                        *[
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/png;base64,"
                                    + base64.b64encode(page).decode()
                                },
                            }
                            for page in pages
                        ],
                    ],
                },
            ],
        }
        encoded = json.dumps(body).encode()
        if len(encoded) > 20 * 1024 * 1024:
            raise ProviderError("PROVIDER_PAYLOAD_TOO_LARGE")
        timeout = httpx.Timeout(settings.provider_timeout_seconds, connect=10, write=20, pool=10)
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    content=encoded,
                )
        except httpx.ReadTimeout as exc:
            raise ProviderError("PROVIDER_READ_TIMEOUT") from exc
        except httpx.ConnectTimeout as exc:
            raise ProviderError("PROVIDER_CONNECT_TIMEOUT") from exc
        except httpx.TransportError as exc:
            raise ProviderError("PROVIDER_TRANSPORT_FAILURE") from exc
        if response.status_code == 429:
            try:
                message = response.json().get("error", {}).get("message", "")
            except ValueError:
                message = ""
            # Whitelist quota numbers/scope only; never retain org IDs or upstream bodies.
            quota = re.findall(
                r"tokens per (?:minute|day)|requests per (?:minute|day)|"
                r"(?:Limit|Used|Requested)\s+\d+|try again in [\d.hms ]+",
                message,
            )
            raise ProviderError(
                "PROVIDER_RATE_LIMITED",
                details={
                    "quota_summary": "; ".join(quota),
                    "retry_after": response.headers.get("retry-after"),
                    "remaining_requests": response.headers.get("x-ratelimit-remaining-requests"),
                    "remaining_tokens": response.headers.get("x-ratelimit-remaining-tokens"),
                    "reset_tokens": response.headers.get("x-ratelimit-reset-tokens"),
                },
            )
        if response.status_code in {500, 502, 503, 504}:
            raise ProviderError("PROVIDER_UNAVAILABLE")
        if response.status_code in {401, 403}:
            raise ProviderError("PROVIDER_ACCESS_DENIED")
        if response.status_code != 200:
            raise ProviderError("PROVIDER_REQUEST_REJECTED")
        try:
            payload = response.json()
            choice = payload["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ProviderError("PROVIDER_INCOMPLETE_OUTPUT")
            invoice = Invoice.model_validate_json(choice["message"]["content"])
            usage = payload.get("usage") or {}
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise ProviderError("PROVIDER_INVALID_SCHEMA") from exc
        return Extraction(
            invoice,
            "groq",
            settings.groq_model,
            {
                "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"),
                "provider_request_id": payload.get("id"),
                "cloud_requests": 1,
                "prompt_version": GROQ_PROMPT_VERSION,
                "estimated_cost_usd": None,
                "pricing_version": None,
                "cost_note": "Billing tier not verified; consult provider usage.",
            },
        )
