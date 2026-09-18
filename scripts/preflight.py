"""Read-only local rehearsal checks. Makes no cloud inference request."""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings  # noqa: E402


def main():
    failed = False
    headers = {"Authorization": f"Bearer {settings.operator_token.get_secret_value()}"}
    with httpx.Client(timeout=5, trust_env=False) as client:
        try:
            ready = client.get("http://127.0.0.1:8000/health/ready")
            config = client.get("http://127.0.0.1:8000/api/v1/config", headers=headers)
            config.raise_for_status()
            active = config.json()
            failed |= ready.status_code != 200
            print(f"API/database/worker: {'ready' if ready.status_code == 200 else 'not ready'}")
            print(f"Active provider: {active['provider']} · page limit: {active['max_pages']}")
            if active["provider"] != settings.provider:
                print("Restart needed: the running provider differs from .env.")
                failed = True
            jobs = client.get("http://127.0.0.1:8000/api/v1/jobs", headers=headers)
            jobs.raise_for_status()
            pending = sum(j["status"] in {"QUEUED", "PROCESSING"} for j in jobs.json())
            print(f"Pending jobs in latest 100: {pending}")
            failed |= pending > 0
        except (httpx.HTTPError, ValueError, KeyError):
            print("Local API unavailable or operator authentication failed.")
            failed = True
        if settings.local_fallback_enabled or settings.provider == "ollama":
            try:
                response = client.get("http://127.0.0.1:11434/api/tags")
                response.raise_for_status()
                installed = any(
                    m["name"] == settings.ollama_model for m in response.json()["models"]
                )
                print(f"Local fallback model: {'installed' if installed else 'missing'}")
                failed |= not installed
            except (httpx.HTTPError, ValueError, KeyError):
                print("Local fallback server is not running.")
                failed = True
    for filename in (
        "01-northline-clean.pdf",
        "02-alder-scanned-discrepancy.pdf",
        "03-meridian-missing-date.pdf",
    ):
        exists = (Path("output/pdf") / filename).is_file()
        print(f"{filename}: {'present' if exists else 'missing'}")
        failed |= not exists
    print("No cloud request made. This does not prove cloud availability or remaining quota.")
    print("Before recording Groq, allow at least a minute after the last extraction; limits vary.")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
