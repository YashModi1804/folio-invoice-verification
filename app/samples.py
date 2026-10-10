"""Synthetic fixtures, never results for arbitrary customer uploads."""

from decimal import Decimal
from pathlib import Path

import pymupdf

from app.domain.models import Invoice

SAMPLES = {
    "clean": ("Northline Studio", "All checks pass", "1250.00", 0.98),
    "variance": ("Northline Studio", "$50 total mismatch", "1300.00", 0.98),
    "uncertain": ("Northline Studio", "Date needs a second look", "1250.00", 0.62),
    "helixpoint": ("HelixPoint", "18 lines · $125 printed-total error", "60283.67", 0.95),
}


def sample_invoice(kind: str) -> Invoice:
    if kind == "helixpoint":
        return helixpoint_invoice()
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
    if kind == "helixpoint":
        return (Path(__file__).parent / "assets/helixpoint-enterprise.pdf").read_bytes()
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


def helixpoint_invoice() -> Invoice:
    """Labeled synthetic extraction for the enterprise demonstration document."""
    items = [
        ("Managed 48-port network switches", "4", "1245.00"),
        ("Enterprise wireless access points", "18", "298.00"),
        ("10G SFP+ transceiver modules", "24", "89.50"),
        ("Rackmount UPS 3000VA", "3", "1595.00"),
        ("UPS replacement battery modules", "6", "412.00"),
        ("Certified CAT6 cable runs", "40", "72.50"),
        ("24-port patch panels", "4", "185.00"),
        ("CAT6 patch leads, 2 m", "120", "9.75"),
        ("Pre-installation site survey", "2", "975.00"),
        ("Perimeter firewall appliances", "2", "2420.00"),
        ("Secure endpoint gateways", "6", "815.00"),
        ("Network configuration, engineer-days", "5", "1250.00"),
        ("On-site commissioning, engineer-days", "4", "1125.00"),
        ("Serialized asset tagging", "126", "6.25"),
        ("Environmental rack monitors", "8", "236.00"),
        ("Three-year support extension", "3", "1350.00"),
        ("Remote rollout coordination, days", "3", "820.00"),
        ("As-built documentation and handover", "1", "1580.00"),
    ]

    def field(value, page=1):
        return {
            "value": value,
            "confidence": 0.95,
            "evidence": [{"page_number": page, "text": str(value)}],
        }

    subtotal = sum((Decimal(q) * Decimal(price) for _, q, price in items), Decimal())
    return Invoice.model_validate(
        {
            "vendor_name": field("HELIXPOINT"),
            "vendor_tax_id": {"value": None, "confidence": 0, "evidence": []},
            "invoice_number": field("HPI-2026-1048"),
            "invoice_date": field("2026-10-02"),
            "currency": field("USD"),
            "subtotal": field(subtotal, 2),
            "tax_amount": field("2484.17", 2),
            "shipping_amount": field("420.00", 2),
            "discount_amount": field("500.00", 2),
            "total_amount": field(
                subtotal
                + Decimal("2484.17")
                + Decimal("420.00")
                - Decimal("500.00")
                + Decimal("125.00"),
                2,
            ),
            "line_items": [
                {
                    "description": description,
                    "quantity": quantity,
                    "unit_price": price,
                    "line_total": str(Decimal(quantity) * Decimal(price)),
                }
                for description, quantity, price in items
            ],
        }
    )
