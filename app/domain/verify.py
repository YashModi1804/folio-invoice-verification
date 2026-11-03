from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.domain.models import Check, Invoice

CENT = Decimal("0.01")
SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP"}


def rounded(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def math_validated(checks: list[Check]) -> bool | None:
    """Summarize the effective checks without treating inconclusive work as a pass."""
    if any(check.state == "FAIL" for check in checks):
        return False
    if not checks or any(check.state == "NOT_APPLICABLE" for check in checks):
        return None
    return True


def compare(code: str, expected: Decimal | None, observed: Decimal | None) -> Check:
    if expected is None or observed is None:
        return Check(code=code, state="NOT_APPLICABLE", expected=expected, observed=observed)
    variance = observed - expected
    return Check(
        code=code,
        state="PASS" if abs(variance) <= CENT else "FAIL",
        expected=expected,
        observed=observed,
        variance=variance,
    )


def verify(invoice: Invoice, *, line_items_complete: bool = True) -> list[Check]:
    # Two 16-digit operands plus a 500-line sum need more than Decimal's default
    # 28 digits. This bounded context preserves cents even for extreme valid input.
    with localcontext() as context:
        context.prec = 40
        checks = []
        complete = bool(invoice.line_items) and line_items_complete
        subtotal = Decimal("0")
        for index, item in enumerate(invoice.line_items):
            expected = None
            if item.quantity is not None and item.unit_price is not None:
                expected = rounded(item.quantity * item.unit_price)
                subtotal += expected
            if expected is None or item.line_total is None:
                complete = False
            checks.append(compare(f"LINE_{index + 1}", expected, item.line_total))
        checks.append(compare("SUBTOTAL", subtotal if complete else None, invoice.subtotal.value))
        operands = [
            invoice.subtotal.value,
            invoice.tax_amount.value,
            invoice.shipping_amount.value,
            invoice.discount_amount.value,
        ]
        total = None
        if all(value is not None for value in operands) and not invoice.tax_inclusive:
            # Providers often preserve a printed "-120.00" discount. Treat either
            # representation as the same discount magnitude; retain source evidence.
            total = rounded(operands[0] + operands[1] + operands[2] - abs(operands[3]))
        checks.append(compare("TOTAL", total, invoice.total_amount.value))
        return checks
