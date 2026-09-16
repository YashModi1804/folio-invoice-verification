from app.domain.models import Check, Invoice
from app.domain.verify import SUPPORTED_CURRENCIES

CORE_FIELDS = (
    "vendor_name", "invoice_number", "invoice_date", "currency", "subtotal",
    "tax_amount", "shipping_amount", "discount_amount", "total_amount",
)


def route(invoice: Invoice, checks: list[Check], threshold: float = 0.85,
          page_count: int = 20) -> tuple[str, list[str]]:
    reasons = []
    for name in CORE_FIELDS:
        field = getattr(invoice, name)
        if field.value is None or (isinstance(field.value, str) and not field.value.strip()):
            reasons.append(f"MISSING_{name.upper()}")
        if field.confidence < threshold:
            reasons.append(f"LOW_CONFIDENCE_{name.upper()}")
        if not field.evidence or any(e.page_number > page_count for e in field.evidence):
            reasons.append(f"MISSING_EVIDENCE_{name.upper()}")
    if invoice.currency.value not in SUPPORTED_CURRENCIES:
        reasons.append("UNSUPPORTED_CURRENCY")
    if invoice.ambiguous_document:
        reasons.append("MULTIPLE_OR_AMBIGUOUS_DOCUMENTS")
    if invoice.tax_inclusive:
        reasons.append("TAX_INCLUSIVE_REQUIRES_REVIEW")
    for check in checks:
        if check.state != "PASS":
            reasons.append(f"{check.code}_{check.state}")
    if not checks:
        reasons.append("NO_VERIFICATION_CHECKS")
    return ("REQUIRES_HUMAN_REVIEW" if reasons else "AUTO_APPROVED", reasons)
