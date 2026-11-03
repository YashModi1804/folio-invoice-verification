from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.models import Check, Invoice
from app.domain.verify import compare, math_validated, rounded, verify
from app.samples import sample_invoice


@pytest.mark.parametrize(
    "observed,state", [("10.00", "PASS"), ("10.01", "PASS"), ("10.02", "FAIL"), ("9.98", "FAIL")]
)
def test_tolerance(observed, state):
    assert compare("TOTAL", Decimal("10"), Decimal(observed)).state == state


def test_missing_is_not_zero():
    assert compare("TOTAL", None, Decimal("0")).state == "NOT_APPLICABLE"


def test_rounding_is_decimal_half_up():
    assert rounded(Decimal("2.345")) == Decimal("2.35")


def test_partial_line_coverage_does_not_create_a_false_subtotal_variance():
    checks = verify(sample_invoice("clean"), line_items_complete=False)
    assert checks[-2].code == "SUBTOTAL"
    assert checks[-2].state == "NOT_APPLICABLE"


@pytest.mark.parametrize(
    "states,expected",
    [
        ([], None),
        (["PASS"], True),
        (["PASS", "NOT_APPLICABLE"], None),
        (["FAIL", "NOT_APPLICABLE"], False),
    ],
)
def test_math_summary_does_not_claim_inconclusive_checks_passed(states, expected):
    checks = [Check(code=f"CHECK_{index}", state=state) for index, state in enumerate(states)]
    assert math_validated(checks) is expected


def test_largest_valid_line_products_and_subtotal_remain_reviewable():
    invoice = sample_invoice("clean")
    line = invoice.line_items[0]
    line.quantity = Decimal("999999999999.9999")
    line.unit_price = Decimal("999999999999.9999")
    invoice.line_items = [line] * 500
    invoice = Invoice.model_validate(invoice.model_dump())
    checks = verify(invoice)
    assert checks[0].state == "FAIL"
    assert checks[0].expected == Decimal("999999999999999800000000.00")
    assert checks[-2].state == "FAIL"
    assert checks[-2].expected == Decimal("499999999999999900000000000.00")
    assert math_validated(checks) is False


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_money_is_rejected_at_the_contract_boundary(value):
    data = sample_invoice("clean").model_dump(mode="json")
    data["line_items"][0]["quantity"] = value
    with pytest.raises(ValidationError):
        Invoice.model_validate(data)
