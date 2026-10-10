"""Build a synthetic enterprise invoice for live extraction evaluation."""

from decimal import Decimal
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf/05-helixpoint-enterprise-discrepancy.pdf"
FONT_DIR = Path(__import__("reportlab").__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("InvoiceSans", str(FONT_DIR / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("InvoiceSansBold", str(FONT_DIR / "VeraBd.ttf")))

INK = HexColor("#21343B")
MUTED = HexColor("#61757B")
RULE = HexColor("#DCE5E7")
PALE = HexColor("#F2F6F6")

ITEMS = [
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


def money(amount: Decimal) -> str:
    return f"{amount:,.2f}"


def label(c: canvas.Canvas, x: float, y: float, value: str, size: int = 9) -> None:
    c.setFillColor(MUTED)
    c.setFont("InvoiceSans", size)
    c.drawString(x, y, value)


def value(
    c: canvas.Canvas,
    x: float,
    y: float,
    content: str,
    size: int = 9,
    right: bool = False,
    bold: bool = False,
) -> None:
    c.setFillColor(INK)
    c.setFont("InvoiceSansBold" if bold else "InvoiceSans", size)
    (c.drawRightString if right else c.drawString)(x, y, content)


def page_header(c: canvas.Canvas, page_number: int) -> None:
    value(c, 42, 751, "HELIXPOINT", 19, bold=True)
    label(c, 42, 734, "INFRASTRUCTURE SERVICES  /  SYNTHETIC VENDOR", 8)
    value(c, 570, 750, "TAX INVOICE", 16, right=True, bold=True)
    label(c, 445, 732, "HPI-2026-1048  /  USD", 9)
    c.setStrokeColor(INK)
    c.line(42, 717, 570, 717)

    for x, caption, line1, line2 in [
        (42, "BILL TO", "Crestfield Manufacturing Group", "500 Example Plaza, Chicago, IL 60601"),
        (
            313,
            "SHIP TO",
            "Crestfield / West Distribution Center",
            "88 Test Logistics Way, Reno, NV 89502",
        ),
    ]:
        label(c, x, 697, caption, 8)
        value(c, x, 679, line1, 9, bold=True)
        value(c, x, 663, line2, 8)

    fields = [
        ("Invoice date", "2026-10-02"),
        ("Due date", "2026-11-01"),
        ("Purchase order", "PO-87420-IT"),
        ("Work order", "NW-2247"),
    ]
    for index, (caption, content) in enumerate(fields):
        x = 42 + (index % 2) * 271
        y = 632 - (index // 2) * 29
        label(c, x, y, caption, 8)
        value(c, x + 116, y, content, 8, bold=True)

    c.setFillColor(PALE)
    c.rect(42, 548, 528, 26, fill=1, stroke=0)
    value(c, 51, 557, "ITEM / DESCRIPTION", 8, bold=True)
    value(c, 397, 557, "QTY", 8, right=True, bold=True)
    value(c, 477, 557, "UNIT USD", 8, right=True, bold=True)
    value(c, 559, 557, "AMOUNT", 8, right=True, bold=True)
    label(c, 42, 37, "SYNTHETIC EVALUATION DOCUMENT - NO REAL TRANSACTION", 7)
    label(c, 527, 37, f"PAGE {page_number} / 2", 7)


def draw_items(c: canvas.Canvas, rows: list[tuple[str, str, str]], offset: int) -> None:
    for position, (description, quantity, unit_price) in enumerate(rows):
        y = 529 - position * 35
        value(c, 51, y, f"{offset + position + 1:02d}  {description}", 8)
        value(c, 397, y, quantity, 8, right=True)
        value(c, 477, y, money(Decimal(unit_price)), 8, right=True)
        line_total = Decimal(quantity) * Decimal(unit_price)
        value(c, 559, y, money(line_total), 8, right=True)
        c.setStrokeColor(RULE)
        c.line(42, y - 12, 570, y - 12)


def build() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT), pagesize=letter, invariant=1)
    c.setTitle("HelixPoint enterprise infrastructure invoice - synthetic evaluation")
    c.setAuthor("Folio synthetic evaluation")

    page_header(c, 1)
    draw_items(c, ITEMS[:9], 0)
    label(c, 51, 184, "Continued on page 2. Totals and remittance details follow.", 9)
    label(c, 51, 160, "Program: West distribution-center network modernization", 8)
    label(c, 51, 144, "Cost center: 440-IT  |  Acceptance reference: CWG-WDC-09", 8)
    c.showPage()

    page_header(c, 2)
    draw_items(c, ITEMS[9:], 9)
    subtotal = sum((Decimal(q) * Decimal(p) for _, q, p in ITEMS), Decimal("0"))
    tax = Decimal("2484.17")
    freight = Decimal("420.00")
    discount = Decimal("500.00")
    calculated_total = subtotal + tax + freight - discount
    printed_total = calculated_total + Decimal("125.00")

    label(c, 51, 193, "Tax basis: equipment and installation; tax shown as billed.", 8)
    label(c, 51, 178, "PO ceiling $95,000 is authorization, not an invoice charge.", 8)
    label(c, 51, 163, "Credit memo CM-11842 is separate and not applied here.", 8)
    for index, (caption, amount) in enumerate(
        [
            ("Items subtotal", subtotal),
            ("Sales tax", tax),
            ("Freight", freight),
            ("Contract discount", discount),
        ]
    ):
        y = 194 - index * 23
        label(c, 385, y, caption, 8)
        value(c, 559, y, money(amount), 9, right=True)
    c.setFillColor(INK)
    c.rect(375, 72, 195, 28, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("InvoiceSansBold", 10)
    c.drawString(384, 82, "TOTAL DUE USD")
    c.drawRightString(560, 82, money(printed_total))
    label(c, 51, 111, "Terms: Net 30. Quote invoice number with remittance.", 8)
    label(c, 51, 95, "Remittance: synthetic details omitted; do not pay.", 8)
    c.showPage()
    c.save()
    print(
        f"{OUTPUT}\n"
        f"18 lines | subtotal {money(subtotal)} | expected total {money(calculated_total)} "
        f"| printed total {money(printed_total)} | variance +125.00"
    )


if __name__ == "__main__":
    build()
