from dataclasses import dataclass, field
from typing import Protocol

from app.domain.models import Invoice
from app.samples import sample_invoice


class ProviderError(RuntimeError):
    """Safe code only: never propagate upstream response bodies to users."""


@dataclass
class Extraction:
    invoice: Invoice
    provider: str
    model: str
    usage: dict = field(default_factory=dict)


class Provider(Protocol):
    def extract(self, pages: list[bytes], sample: str | None = None) -> Extraction: ...


class FixtureProvider:
    def extract(self, pages: list[bytes], sample: str | None = None) -> Extraction:
        if sample is None:
            raise ProviderError("LIVE_PROVIDER_NOT_CONFIGURED")
        return Extraction(sample_invoice(sample), "fixture", "synthetic-v1",
                          {"input_tokens": None, "output_tokens": None,
                           "estimated_cost_usd": "0", "pricing_version": "fixture-no-api"})
