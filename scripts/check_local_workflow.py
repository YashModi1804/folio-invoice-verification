"""Opt-in acceptance test through the running local API, queue and real model."""

import json
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings  # noqa: E402

CASES = [
    ("01-northline-clean.pdf", "AUTO_APPROVED"),
    ("02-alder-scanned-discrepancy.pdf", "REQUIRES_HUMAN_REVIEW"),
    ("03-meridian-missing-date.pdf", "REQUIRES_HUMAN_REVIEW"),
]


def main():
    results = []
    with httpx.Client(
        base_url="http://127.0.0.1:8000",
        timeout=20,
        trust_env=False,
        headers={"Authorization": f"Bearer {settings.operator_token.get_secret_value()}"},
    ) as client:
        assert client.get("/api/v1/config").json()["provider"] == "ollama", (
            "Select local mode first"
        )
        for filename, expected in CASES:
            path = Path("output/pdf") / filename
            key = str(uuid4())

            def upload(key=key, filename=filename, path=path):
                response = client.post(
                    "/api/v1/documents",
                    headers={"Idempotency-Key": key},
                    files={"file": (filename, path.read_bytes(), "application/pdf")},
                )
                response.raise_for_status()
                return response.json()["job_id"]

            job_id = upload()
            assert upload() == job_id, "Duplicate submission created another job"
            deadline = time.monotonic() + settings.ollama_timeout_seconds + 30
            while time.monotonic() < deadline:
                job = client.get(f"/api/v1/jobs/{job_id}").json()
                if job["status"] not in {"QUEUED", "PROCESSING"}:
                    break
                time.sleep(1)
            results.append(job)
            output = Path("data/evaluations/local-workflow.json")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(results, indent=2) + "\n")
            print(filename, job["status"], job.get("error"), job_id, flush=True)
            assert job["status"] == expected, (
                "Unexpected route; inspect the local evaluation report"
            )
            assert job["mode"] == job["result"]["telemetry"]["provider"] == "ollama"
            assert client.get(f"/api/v1/jobs/{job_id}/pages/1").status_code == 200
            assert client.get(f"/api/v1/jobs/{job_id}/audit").status_code == 200
            if filename.startswith("02"):
                total = next(c for c in job["result"]["checks"] if c["code"] == "TOTAL")
                assert total["variance"] == "50.00"
                assert len(job["result"]["invoice"]["line_items"]) == 6
            if filename.startswith("03"):
                assert job["result"]["invoice"]["invoice_date"]["value"] is None
    print("All three local workflows passed; no review decisions were changed.")


if __name__ == "__main__":
    main()
