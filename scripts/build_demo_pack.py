"""Create synthetic source documents for LIVE extraction, not canned extraction results."""

import json
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pymupdf
import reportlab
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf"
IMAGES = ROOT / "data/demo-pack/images"
INK = HexColor("#203D40")
MUTED = HexColor("#64746F")
PALE = HexColor("#F0F4EE")
FONTS = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("DemoSans", str(FONTS / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("DemoSansBold", str(FONTS / "VeraBd.ttf")))


def text(c, x, y, value, size=10, bold=False, color=INK, right=False):
    c.setFillColor(color)
    c.setFont("DemoSansBold" if bold else "DemoSans", size)
    (c.drawRightString if right else c.drawString)(x, y, str(value))


def page(c, vendor, number, issued, rows, totals, index=1, pages=1):
    text(c, 44, 785, vendor.upper(), 17, True)
    text(c, 44, 765, "Business services / Accounts receivable", 9, color=MUTED)
    text(c, 551, 785, "INVOICE", 13, True, right=True)
    c.setStrokeColor(INK)
    c.line(44, 742, 551, 742)
    text(c, 44, 713, "BILL TO", 8, True, MUTED)
    text(c, 44, 691, "Example Agency LLC", 12, True)
    text(c, 44, 673, "100 Example Avenue, New York, NY 10001", 9)
    text(c, 44, 657, "Project: September operations", 9, color=MUTED)
    for y, label, value in [
        (713, "Invoice number", number),
        (693, "Invoice date", issued),
        (673, "Currency", "USD"),
        (653, "Payment terms", "Net 30"),
    ]:
        text(c, 346, y, label, 9, color=MUTED)
        text(c, 551, y, value, 9, True, right=True)
    c.setFillColor(PALE)
    c.rect(44, 589, 507, 27, fill=1, stroke=0)
    for x, name in [(55, "DESCRIPTION"), (358, "QTY"), (449, "UNIT PRICE"), (540, "AMOUNT")]:
        text(c, x, 599, name, 8, True, right=x > 55)
    y = 566
    for description, quantity, price in rows:
        amount = Decimal(quantity) * Decimal(price)
        text(c, 55, y, description, 10)
        text(c, 358, y, quantity, 10, right=True)
        text(c, 449, y, f"{Decimal(price):,.2f}", 10, right=True)
        text(c, 540, y, f"{amount:,.2f}", 10, True, right=True)
        c.setStrokeColor(PALE)
        c.line(44, y - 15, 551, y - 15)
        y -= 42
    if totals:
        y = min(y - 25, 360)
        for label, amount in zip(
            ["Subtotal", "Tax", "Shipping", "Discount"], totals[:4], strict=True
        ):
            text(c, 360, y, label, 10, color=MUTED)
            text(c, 540, y, amount, 11, right=True)
            y -= 24
        c.setFillColor(INK)
        c.rect(345, y - 22, 206, 42, fill=1, stroke=0)
        text(c, 359, y - 7, "TOTAL USD", 10, True, HexColor("#FFFFFF"))
        text(c, 540, y - 7, totals[4], 16, True, HexColor("#FFFFFF"), right=True)
        text(c, 44, 155, "Thank you for your business.", 12, True)
        text(c, 44, 135, "Reference the invoice number when arranging payment.", 9, color=MUTED)
    else:
        text(c, 44, y - 25, "Continued on page 2. Invoice totals appear on the final page.", 10)
    c.setStrokeColor(PALE)
    c.line(44, 85, 551, 85)
    text(c, 44, 62, "SYNTHETIC EVALUATION DOCUMENT - NO REAL TRANSACTION", 7, color=MUTED)
    text(c, 551, 62, f"{index} / {pages}", 8, color=MUTED, right=True)
    c.showPage()


def make_pdf(filename, vendor, number, issued, rows, totals, scanned=False):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(595, 842), invariant=1)
    c.setTitle(f"{vendor} - {number} - synthetic evaluation")
    c.setAuthor("Folio synthetic test documents")
    if scanned:
        page(c, vendor, number, issued, rows[:3], None, 1, 2)
        page(c, vendor, number, issued, rows[3:], totals, 2, 2)
    else:
        page(c, vendor, number, issued, rows, totals)
    c.save()
    path = OUTPUT / filename
    if scanned:
        # Raster-only grayscale PDF: the model must read the actual page images.
        scan = canvas.Canvas(str(path), pagesize=(595, 842), invariant=1)
        scan.setTitle("Synthetic two-page scanned invoice with printed total discrepancy")
        with pymupdf.open(stream=buffer.getvalue(), filetype="pdf") as source:
            for source_page in source:
                pix = source_page.get_pixmap(
                    matrix=pymupdf.Matrix(1.7, 1.7), colorspace=pymupdf.csGRAY
                )
                scan.drawImage(ImageReader(BytesIO(pix.tobytes("png"))), 0, 0, 595, 842)
                scan.showPage()
        scan.save()
    else:
        path.write_bytes(buffer.getvalue())
    return path


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(parents=True, exist_ok=True)
    make_pdf(
        "01-northline-clean.pdf",
        "Northline Studio",
        "NLS-2026-0914",
        "2026-09-14",
        [
            ("Discovery workshop", "3", "180.00"),
            ("Interface design", "2", "240.00"),
            ("Component documentation", "5", "46.00"),
        ],
        ["1250.00", "100.00", "25.00", "50.00", "1325.00"],
    )
    make_pdf(
        "02-alder-scanned-discrepancy.pdf",
        "Alder Office Supply",
        "ALD-2026-0082",
        "2026-09-12",
        [
            ("Adjustable monitor stands", "8", "62.50"),
            ("Desk organizers", "12", "18.75"),
            ("Task lighting kits", "6", "45.00"),
            ("Ergonomic keyboard trays", "4", "82.50"),
            ("Cable management kits", "10", "24.00"),
            ("Workspace installation", "2", "67.50"),
        ],
        ["1700.00", "136.00", "24.00", "60.00", "1850.00"],
        scanned=True,
    )
    make_pdf(
        "03-meridian-missing-date.pdf",
        "Meridian Research",
        "MER-2026-0047",
        "Pending confirmation",
        [("Market analysis brief", "1", "375.00"), ("Research synthesis", "1", "375.00")],
        ["750.00", "60.00", "0.00", "0.00", "810.00"],
    )
    with pymupdf.open(OUTPUT / "01-northline-clean.pdf") as doc:
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5))
        from PIL import Image

        image = Image.open(BytesIO(pix.tobytes("png")))
        for extension in ("png", "jpg", "webp"):
            image.save(IMAGES / f"northline-clean.{extension}")
        image.transpose(Image.Transpose.ROTATE_90).save(IMAGES / "northline-rotated.png")
    print(
        json.dumps(
            {
                "pdfs": sorted(str(p.relative_to(ROOT)) for p in OUTPUT.glob("*.pdf")),
                "images": sorted(str(p.relative_to(ROOT)) for p in IMAGES.glob("*")),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
