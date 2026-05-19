from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities.field import BaseField
from app.domain.merge.defaults import STRICT_REGISTRY
from app.domain.ports.nomenclature_classifier import NomenclatureArticle


class DocumentObjectField(BaseField[str]):
    merge_registry = STRICT_REGISTRY


@dataclass(kw_only=True, frozen=True)
class Amount:
    value: Decimal | None
    transcription: str | None


@dataclass(kw_only=True, frozen=True)
class Vat:
    amount: Amount | None
    rate: Decimal | None


@dataclass(kw_only=True, frozen=True)
class Payment:
    amount: Amount | None
    vat: Vat
    include_vat: bool | None


@dataclass(kw_only=True, frozen=True)
class TotalAmount:
    total: Payment
    taxes: list[Payment]


@dataclass(kw_only=True, frozen=True)
class TotalAmountField(BaseField[TotalAmount]):
    merge_registry = STRICT_REGISTRY


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
    name: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    total_price: Decimal | None
    unit_of_measurement: str | None


@dataclass(kw_only=True, frozen=True)
class SpecPositionsField(BaseField[list[SpecPosition]]):
    merge_registry = STRICT_REGISTRY


@dataclass(kw_only=True, frozen=True)
class NomenclatureClassification:
    position: SpecPosition
    articles: list[NomenclatureArticle]


@dataclass(kw_only=True, frozen=True)
class NomenclatureClassificationsField(BaseField[list[NomenclatureClassification]]):
    merge_registry = STRICT_REGISTRY
