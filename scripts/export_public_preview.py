"""Export synthetic sample results for the GitHub Pages preview.

This does not read local jobs, documents, credentials, or provider responses.
"""

import json
from pathlib import Path

import pymupdf

from app.domain.routing import route
from app.domain.verify import verify
from app.samples import SAMPLES, sample_invoice, sample_pdf

DESTINATION = Path(__file__).resolve().parents[1] / "web" / "public" / "preview"


def export() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    examples = []
    for kind in SAMPLES:
        invoice = sample_invoice(kind)
        checks = verify(invoice)
        status, reasons = route(invoice, checks, page_count=2)
        with pymupdf.open(stream=sample_pdf(kind), filetype="pdf") as document:
            for page_number, page in enumerate(document, start=1):
                image = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
                (DESTINATION / f"{kind}-{page_number}.png").write_bytes(image.tobytes("png"))
        fields = invoice.model_dump(mode="json")
        examples.append(
            {
                "kind": kind,
                "job": {
                    "job_id": f"preview-{kind}",
                    "correlation_id": f"synthetic-{kind}",
                    "filename": f"northline-{kind}.pdf",
                    "status": status,
                    "page_count": 2,
                    "mode": "fixture",
                    "requested_provider": "fixture",
                    "created_at": "",
                    "not_before": None,
                    "error": None,
                    "summary": {
                        key: fields[key]["value"]
                        for key in ("vendor_name", "invoice_number", "total_amount", "currency")
                    },
                    "result": {
                        "invoice": fields,
                        "checks": [check.model_dump(mode="json") for check in checks],
                        "route_reasons": reasons,
                        "math_validated": all(check.state == "PASS" for check in checks),
                        "telemetry": {
                            "provider": "fixture",
                            "model": "synthetic-v1",
                            "latency_ms": 0,
                            "input_tokens": None,
                            "output_tokens": None,
                            "estimated_cost_usd": "0",
                            "prompt_version": "fixture-v1",
                            "schema_version": "1",
                            "pricing_version": "fixture-no-api",
                        },
                    },
                },
            }
        )
    (DESTINATION / "data.json").write_text(json.dumps(examples, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    export()
