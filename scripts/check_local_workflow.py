"""Opt-in acceptance test through the running local API, queue and real model."""

import argparse
import json
import sys
import time
from decimal import Decimal
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

EXPECTED = {
    "01": (
        "NLS-2026-0914",
        "2026-09-14",
        ["1250", "100", "25", "50", "1325"],
        [("3", "180", "540"), ("2", "240", "480"), ("5", "46", "230")],
    ),
    "02": (
        "ALD-2026-0082",
        "2026-09-12",
        ["1700", "136", "24", "60", "1850"],
        [
            ("8", "62.5", "500"),
            ("12", "18.75", "225"),
            ("6", "45", "270"),
            ("4", "82.5", "330"),
            ("10", "24", "240"),
            ("2", "67.5", "135"),
        ],
    ),
    "03": (
        "MER-2026-0047",
        None,
        ["750", "60", "0", "0", "810"],
        [("1", "375", "375"), ("1", "375", "375")],
    ),
}


def check_ground_truth(filename, invoice):
    number, date, amounts, lines = EXPECTED[filename[:2]]
    assert invoice["invoice_number"]["value"] == number
    assert invoice["invoice_date"]["value"] == date
    assert invoice["currency"]["value"] == "USD"
    assert invoice["tax_inclusive"] is False
    assert invoice["ambiguous_document"] is False
    for name, value in zip(
        ("subtotal", "tax_amount", "shipping_amount", "discount_amount", "total_amount"),
        amounts,
        strict=True,
    ):
        assert Decimal(invoice[name]["value"]) == Decimal(value), name
    assert len(invoice["line_items"]) == len(lines)
    for line, values in zip(invoice["line_items"], lines, strict=True):
        for name, value in zip(("quantity", "unit_price", "line_total"), values, strict=True):
            assert Decimal(line[name]) == Decimal(value), name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["ollama", "gemini", "groq"], default="ollama")
    parser.add_argument("--output", type=Path, default=Path("data/evaluations/local-workflow.json"))
    parser.add_argument("--case", choices=["01", "02", "03"])
    parser.add_argument("--interval", type=int, default=0, help="Seconds between cloud jobs")
    parser.add_argument("--require-primary", action="store_true", help="Fail if fallback was used")
    args = parser.parse_args()
    results = []
    with httpx.Client(
        base_url="http://127.0.0.1:8000",
        timeout=20,
        trust_env=False,
        headers={"Authorization": f"Bearer {settings.operator_token.get_secret_value()}"},
    ) as client:
        assert client.get("/api/v1/config").json()["provider"] == args.provider, (
            "The running API must match the selected evaluation provider"
        )
        for filename, expected in CASES:
            if args.case and not filename.startswith(args.case):
                continue
            if results and args.interval > 0:
                time.sleep(args.interval)
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
            deadline = (
                time.monotonic()
                + settings.ollama_timeout_seconds
                + settings.provider_timeout_seconds
                + 30
            )
            while time.monotonic() < deadline:
                job = client.get(f"/api/v1/jobs/{job_id}").json()
                if job["status"] not in {"QUEUED", "PROCESSING"}:
                    break
                time.sleep(1)
            results.append(job)
            output = args.output
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(results, indent=2) + "\n")
            print(filename, job["status"], job.get("error"), job_id, flush=True)
            assert job["status"] == expected, (
                "Unexpected route; inspect the local evaluation report"
            )
            check_ground_truth(filename, job["result"]["invoice"])
            assert job["requested_provider"] == args.provider
            assert job["mode"] == job["result"]["telemetry"]["provider"]
            if args.require_primary:
                assert job["mode"] == args.provider, "Primary unavailable; result used fallback"
            if job["mode"] != args.provider:
                assert job["result"]["telemetry"]["fallback_reason"]
            assert client.get(f"/api/v1/jobs/{job_id}/pages/1").status_code == 200
            assert client.get(f"/api/v1/jobs/{job_id}/audit").status_code == 200
            if filename.startswith("02"):
                total = next(c for c in job["result"]["checks"] if c["code"] == "TOTAL")
                assert total["variance"] == "50.00"
                assert len(job["result"]["invoice"]["line_items"]) == 6
            if filename.startswith("03"):
                assert job["result"]["invoice"]["invoice_date"]["value"] is None
    print(f"All {len(results)} workflows passed; no review decisions were changed.")


if __name__ == "__main__":
    main()
