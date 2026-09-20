from app.domain.page_plan import make_plan


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
