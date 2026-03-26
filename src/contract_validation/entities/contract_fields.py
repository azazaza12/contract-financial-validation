from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities.field import BaseField
from app.domain.merge.defaults import FLEXIBLE_REGISTRY, STRICT_REGISTRY


class DocumentObjectField(BaseField[str]):
    merge_registry = STRICT_REGISTRY


@dataclass(kw_only=True, frozen=True)
class Amount:
    value: Decimal
    transcription: str | None


@dataclass(kw_only=True, frozen=True)
class Vat:
    amount: Amount | None
    rate: Decimal | None


@dataclass(kw_only=True, frozen=True)
class Payment:
    amount: Amount | None
    vat: Vat
    include_vat: bool


@dataclass(kw_only=True, frozen=True)
class TotalAmount:
    total: Payment
    taxes: list[Payment]


@dataclass(kw_only=True, frozen=True)
class TotalAmountField(BaseField[TotalAmount]):
    merge_registry = FLEXIBLE_REGISTRY


@dataclass(kw_only=True, frozen=True)
class AdvancePayment:
    percent: Decimal | None
    total: Payment | None
    payments: list[Payment]


@dataclass(kw_only=True, frozen=True)
class AdvancePaymentsField(BaseField[list[AdvancePayment]]):
    merge_registry = STRICT_REGISTRY


@dataclass(kw_only=True, frozen=True)
class SpecPosition:
    name: str
    quantity: Decimal
    unit_price: Decimal
    total_price: Decimal
    unit_of_measurement: str


@dataclass(kw_only=True, frozen=True)
class SpecPositionsField(BaseField[list[SpecPosition]]):
    merge_registry = STRICT_REGISTRY
