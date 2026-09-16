"""Explicit opt-in live evaluation. Never imported by the default unit tests."""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.domain.routing import route  # noqa: E402
from app.domain.verify import verify  # noqa: E402
from app.gemini import GeminiProvider  # noqa: E402
from app.providers import ProviderError  # noqa: E402
from app.storage import inspect, render  # noqa: E402


def evaluate(path: Path) -> dict:
    start = time.monotonic()
    data = path.read_bytes()
    media, pages = inspect(data, path.name)
    try:
        extraction = GeminiProvider().extract(render(data, media))
        checks = verify(extraction.invoice)
        status, reasons = route(extraction.invoice, checks, page_count=pages)
        return {
            "file": str(path),
            "status": status,
            "route_reasons": reasons,
            "latency_ms": round((time.monotonic() - start) * 1000),
            "invoice": extraction.invoice.model_dump(mode="json"),
            "checks": [c.model_dump(mode="json") for c in checks],
            "provider": extraction.provider,
            "model": extraction.model,
            "usage": extraction.usage,
        }
    except ProviderError as exc:
        return {
            "file": str(path),
            "status": "FAILED",
            "error": str(exc),
            "latency_ms": round((time.monotonic() - start) * 1000),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/evaluations/live-results.json"))
    args = parser.parse_args()
    results = []
    for path in args.files:
        result = evaluate(path)
        results.append(result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2) + "\n")
        print(
            json.dumps(
                {k: result[k] for k in ("file", "status", "latency_ms")}
                | {"error": result.get("error"), "reasons": result.get("route_reasons")}
            ),
            flush=True,
        )
        if result.get("error") in {
            "PROVIDER_UNAVAILABLE",
            "PROVIDER_REQUEST_REJECTED",
            "PROVIDER_RATE_LIMITED",
        }:
            break
    raise SystemExit(1 if any(r["status"] == "FAILED" for r in results) else 0)


if __name__ == "__main__":
    main()
