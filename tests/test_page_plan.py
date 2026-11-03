from app.domain.models import Evidence
from app.domain.page_plan import make_plan, remap_evidence_pages
from app.domain.routing import route
from app.domain.verify import verify
from app.samples import sample_invoice


def test_page_plan_prefers_header_and_final_totals_with_explicit_coverage_gap():
    plan = make_plan(
        [
            "Invoice number A-19\nBill to Example",
            "Description Quantity Unit price",
            "Description Quantity Unit price",
            "Grand total 120.00\nAmount due 120.00",
        ],
        max_pages_per_request=2,
        base_tokens=2_600,
        image_tokens=2_048,
    )
    assert plan.selected_pages == (1, 4)
    assert plan.skipped_pages == (2, 3)
    assert plan.roles == ("HEADER", "LINE_ITEMS", "LINE_ITEMS", "TOTALS")
    assert plan.estimated_tokens == 6_696


def test_page_plan_covers_small_documents_completely():
    plan = make_plan(
        ["Invoice", "Grand total"], max_pages_per_request=2, base_tokens=2, image_tokens=3
    )
    assert plan.selected_pages == (1, 2)
    assert plan.skipped_pages == ()


def test_evidence_cannot_reference_an_image_that_was_not_supplied():
    invoice = sample_invoice("clean")
    invoice.total_amount.evidence = [Evidence(page_number=3, text="Total 1250.00")]
    mapped, invalid = remap_evidence_pages(invoice, (1, 4))
    assert invalid == [{"field": "total_amount", "image_position": 3}]
    assert mapped.total_amount.evidence == []
    assert invoice.total_amount.evidence[0].page_number == 3
    status, reasons = route(
        mapped,
        verify(mapped, line_items_complete=False),
        page_count=4,
        complete_page_coverage=False,
        invalid_evidence_reference=bool(invalid),
    )
    assert status == "REQUIRES_HUMAN_REVIEW"
    assert "INVALID_EVIDENCE_PAGE_REFERENCE" in reasons
    assert "MISSING_EVIDENCE_TOTAL_AMOUNT" in reasons
