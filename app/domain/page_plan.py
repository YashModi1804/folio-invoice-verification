"""Safe local page selection for capacity-constrained vision extraction."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PagePlan:
    selected_pages: tuple[int, ...]
    skipped_pages: tuple[int, ...]
    roles: tuple[str, ...]
    estimated_tokens: int


def classify_page(text: str, page_number: int, page_count: int) -> str:
    """Classify from native PDF text only; unclassified pages remain reviewable."""
    content = text.lower()
    if any(term in content for term in ("grand total", "amount due", "balance due", "total due")):
        return "TOTALS"
    if page_number == 1 or any(term in content for term in ("invoice", "bill to", "invoice no")):
        return "HEADER"
    if any(term in content for term in ("quantity", "unit price", "description", "particulars")):
        return "LINE_ITEMS"
    if page_number == page_count:
        return "FINAL_PAGE"
    return "UNCLASSIFIED"


def make_plan(
    page_texts: list[str], *, max_pages_per_request: int, base_tokens: int, image_tokens: int
) -> PagePlan:
    """Prefer a document's header and final totals while never hiding skipped pages."""
    if not page_texts:
        raise ValueError("At least one page is required")
    if max_pages_per_request < 1:
        raise ValueError("At least one page must fit within the provider budget")

    page_count = len(page_texts)
    roles = tuple(
        classify_page(text, page_number, page_count)
        for page_number, text in enumerate(page_texts, start=1)
    )
    candidates = [1]
    totals = [index + 1 for index, role in enumerate(roles) if role == "TOTALS"]
    if totals:
        candidates.append(totals[-1])
    candidates.append(page_count)
    candidates.extend(range(1, page_count + 1))

    selected: list[int] = []
    for page_number in candidates:
        if page_number not in selected and len(selected) < max_pages_per_request:
            selected.append(page_number)
    selected.sort()
    skipped = tuple(page for page in range(1, page_count + 1) if page not in selected)
    return PagePlan(
        selected_pages=tuple(selected),
        skipped_pages=skipped,
        roles=roles,
        estimated_tokens=base_tokens + image_tokens * len(selected),
    )
