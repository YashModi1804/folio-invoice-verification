"""Synthetic fixtures, never results for arbitrary customer uploads."""

import pymupdf

from app.domain.models import Invoice

SAMPLES = {
    "clean": ("Northline Studio", "All checks pass", "1250.00", 0.98),
    "variance": ("Northline Studio", "$50 total mismatch", "1300.00", 0.98),
    "uncertain": ("Northline Studio", "Date needs a second look", "1250.00", 0.62),
}


def sample_invoice(kind: str) -> Invoice:
    vendor, _, total, confidence = SAMPLES[kind]

    def field(value, page=1, score=0.98):
        if value is None:
            return {"value": None, "confidence": 0, "evidence": []}
        return {
            "value": value,
            "confidence": score,
            "evidence": [{"page_number": page, "text": str(value)}],
        }

    return Invoice.model_validate(
        {
            "vendor_name": field(vendor),
            "vendor_tax_id": field(None),
            "invoice_number": field("NS-2026-041"),
            "invoice_date": field("2026-09-14", score=confidence),
            "currency": field("USD"),
            "subtotal": field("1200.00", 2),
            "tax_amount": field("50.00", 2),
            "shipping_amount": field("0.00", 2),
            "discount_amount": field("0.00", 2),
            "total_amount": field(total, 2),
            "line_items": [
                {
                    "description": "Brand strategy workshop",
                    "quantity": "2",
                    "unit_price": "400.00",
                    "line_total": "800.00",
                },
                {
                    "description": "Design system handoff",
                    "quantity": "1",
                    "unit_price": "400.00",
                    "line_total": "400.00",
                },
            ],
        }
    )


def sample_pdf(kind: str) -> bytes:
    invoice = sample_invoice(kind)
    with pymupdf.open() as doc:
        for index in range(2):
            page = doc.new_page(width=595, height=842)
            page.insert_text((48, 65), "NORTHLINE / STUDIO", fontsize=20, color=(0.12, 0.2, 0.24))
            page.insert_text((48, 100), "INVOICE    NS-2026-041", fontsize=13)
            page.insert_text((48, 130), "Issued 2026-09-14  |  Currency USD", fontsize=10)
            page.insert_text((48, 155), "Bill to: Example Agency, 100 Sample Street", fontsize=10)
            if index == 0:
                lines = [
                    "SERVICES                                     QTY      RATE       AMOUNT",
                    "",
                    "Brand strategy workshop                2         400.00       800.00",
                    "Design system handoff                   1         400.00       400.00",
                    "",
                    "Totals continued on page 2.",
                ]
            else:
                lines = [
                    "INVOICE SUMMARY",
                    "",
                    "Subtotal                       1200.00",
                    "Tax                                   50.00",
                    "Shipping                             0.00",
                    "Discount                             0.00",
                    "",
                    f"TOTAL USD                     {invoice.total_amount.value}",
                    "",
                    "Payment terms: net 30 days.",
                ]
            page.insert_text((48, 230), "\n".join(lines), fontsize=12)
            page.insert_text((48, 780), f"SYNTHETIC DEMO DOCUMENT | {index + 1} / 2", fontsize=9)
        return doc.tobytes()
