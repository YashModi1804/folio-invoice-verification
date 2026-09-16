"""Offline guardrail regression evaluation; not a live extraction accuracy benchmark."""

import json

from app.domain.routing import route
from app.domain.verify import verify
from app.samples import SAMPLES, sample_invoice


def main():
    results = []
    for kind in SAMPLES:
        invoice = sample_invoice(kind)
        checks = verify(invoice)
        status, reasons = route(invoice, checks, page_count=2)
        expected = "AUTO_APPROVED" if kind == "clean" else "REQUIRES_HUMAN_REVIEW"
        results.append(
            {
                "sample": kind,
                "expected": expected,
                "actual": status,
                "passed": expected == status,
                "reasons": reasons,
            }
        )
    print(
        json.dumps(
            {"scope": "offline routing regression, not extraction accuracy", "results": results},
            indent=2,
        )
    )
    raise SystemExit(0 if all(row["passed"] for row in results) else 1)


if __name__ == "__main__":
    main()
