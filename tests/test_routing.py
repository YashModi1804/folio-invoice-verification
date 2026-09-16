from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.routing import route
from app.domain.verify import verify
from app.samples import sample_invoice


@pytest.mark.parametrize("field", ["vendor_name", "invoice_number", "invoice_date", "currency",
                                  "subtotal", "tax_amount", "shipping_amount", "discount_amount",
                                  "total_amount"])
def test_missing_fields_block_automatic_approval(field):
    invoice = sample_invoice("clean")
    getattr(invoice, field).value = None
    assert route(invoice, verify(invoice))[0] == "REQUIRES_HUMAN_REVIEW"


def test_evidence_page_bounds():
    invoice = sample_invoice("clean")
    assert route(invoice, verify(invoice), page_count=1)[0] == "REQUIRES_HUMAN_REVIEW"


@pytest.mark.parametrize("condition", ["tax_inclusive", "ambiguous_document"])
def test_unsupported_layouts_route_to_review(condition):
    invoice = sample_invoice("clean")
    setattr(invoice, condition, True)
    assert route(invoice, verify(invoice))[0] == "REQUIRES_HUMAN_REVIEW"


def test_line_mismatch_blocks_even_when_total_matches():
    invoice = sample_invoice("clean")
    invoice.line_items[0].line_total = Decimal("700")
    checks = verify(invoice)
    assert checks[-1].state == "PASS"
    assert route(invoice, checks)[0] == "REQUIRES_HUMAN_REVIEW"


def test_missing_lines_are_not_trusted():
    invoice = sample_invoice("clean")
    invoice.line_items = []
    assert route(invoice, verify(invoice))[0] == "REQUIRES_HUMAN_REVIEW"


def test_nonfinite_money_rejected():
    data = sample_invoice("clean").model_dump(mode="json")
    data["total_amount"]["value"] = "NaN"
    with pytest.raises(ValidationError):
        type(sample_invoice("clean")).model_validate(data)
