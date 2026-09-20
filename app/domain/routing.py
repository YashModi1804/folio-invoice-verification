from app.domain.models import Check, Invoice
from app.domain.verify import SUPPORTED_CURRENCIES

CORE_FIELDS = (
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "currency",
    "subtotal",
    "tax_amount",
    "shipping_amount",
    "discount_amount",
    "total_amount",
)


def route(
    invoice: Invoice,
    checks: list[Check],
    threshold: float = 0.85,
    page_count: int = 20,
    complete_page_coverage: bool = True,
) -> tuple[str, list[str]]:
    reasons = []
    has_invalid_evidence_reference = False
    for name in CORE_FIELDS:
        field = getattr(invoice, name)
        if field.value is None or (isinstance(field.value, str) and not field.value.strip()):
            reasons.append(f"MISSING_{name.upper()}")
        if field.confidence < threshold:
            reasons.append(f"LOW_CONFIDENCE_{name.upper()}")
        valid_evidence = [
            evidence for evidence in field.evidence if 1 <= evidence.page_number <= page_count
        ]
        if not valid_evidence:
            reasons.append(f"MISSING_EVIDENCE_{name.upper()}")
        if len(valid_evidence) != len(field.evidence):
            has_invalid_evidence_reference = True
    if has_invalid_evidence_reference:
        # Keep valid citations useful, but never let an impossible citation pass silently.
        reasons.append("INVALID_EVIDENCE_PAGE_REFERENCE")
    if invoice.currency.value not in SUPPORTED_CURRENCIES:
        reasons.append("UNSUPPORTED_CURRENCY")
    if any(
        getattr(invoice, name).value is not None and getattr(invoice, name).value < 0
        for name in ("subtotal", "tax_amount", "shipping_amount", "total_amount")
    ):
        reasons.append("NEGATIVE_AMOUNT_REQUIRES_REVIEW")
    if any(
        value is not None and value < 0
        for item in invoice.line_items
        for value in (item.quantity, item.unit_price, item.line_total)
    ):
        reasons.append("NEGATIVE_LINE_REQUIRES_REVIEW")
    if invoice.ambiguous_document:
        reasons.append("MULTIPLE_OR_AMBIGUOUS_DOCUMENTS")
    if invoice.tax_inclusive:
        reasons.append("TAX_INCLUSIVE_REQUIRES_REVIEW")
    for check in checks:
        if check.state != "PASS":
            reasons.append(f"{check.code}_{check.state}")
    if not checks:
        reasons.append("NO_VERIFICATION_CHECKS")
    if not complete_page_coverage:
        reasons.append("INCOMPLETE_PAGE_COVERAGE")
    return ("REQUIRES_HUMAN_REVIEW" if reasons else "AUTO_APPROVED", reasons)
