from decimal import Decimal

import pytest

from app.domain.verify import compare, rounded, verify
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
