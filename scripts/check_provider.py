"""Inspect model availability without displaying credentials or making inference calls."""

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings  # noqa: E402


def main():
    key = settings.gemini_api_key.get_secret_value()
    if not key:
        raise SystemExit("GEMINI_API_KEY is empty in the saved .env.")
    try:
        response = httpx.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": key},
            timeout=30,
        )
    except httpx.TransportError:
        raise SystemExit("Model discovery failed: network transport unavailable.") from None
    print(
        json.dumps(
            {
                "http_status": response.status_code,
                "configured_model": settings.gemini_model,
                "available_generation_models": [
                    m["name"].removeprefix("models/")
                    for m in response.json().get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])
                ],
            },
            indent=2,
        )
    )
    raise SystemExit(0 if response.status_code == 200 else 1)


if __name__ == "__main__":
    main()
