from datetime import date
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")
Money = Annotated[Decimal, Field(allow_inf_nan=False, max_digits=16, decimal_places=4)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Contract):
    page_number: int = Field(ge=1, le=20)
    text: str = Field(min_length=1, max_length=300)


class ExtractedField(Contract, Generic[T]):
    value: T | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list, max_length=5)


class LineItem(Contract):
    description: str = Field(max_length=500)
    quantity: Money | None = None
    unit_price: Money | None = None
    line_total: Money | None = None


class Invoice(Contract):
    vendor_name: ExtractedField[str]
    vendor_tax_id: ExtractedField[str]
    invoice_number: ExtractedField[str]
    invoice_date: ExtractedField[date]
    currency: ExtractedField[str]
    subtotal: ExtractedField[Money]
    tax_amount: ExtractedField[Money]
    shipping_amount: ExtractedField[Money]
    discount_amount: ExtractedField[Money]
    total_amount: ExtractedField[Money]
    line_items: list[LineItem] = Field(max_length=500)
    ambiguous_document: bool = False
    tax_inclusive: bool = False


class Check(Contract):
    code: str
    state: Literal["PASS", "FAIL", "NOT_APPLICABLE"]
    expected: Money | None = None
    observed: Money | None = None
    variance: Money | None = None
    tolerance: Money = Decimal("0.01")


class Decision(Contract):
    action: Literal["approve", "reject"]
    note: str = Field(min_length=3, max_length=1000)
    corrected_invoice: Invoice | None = None
