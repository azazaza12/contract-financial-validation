from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities.field import BaseField
from app.domain.merge.defaults import STRICT_REGISTRY
from app.domain.service.nomenclature_classifier import NomenclatureArticle


class DocumentObjectField(BaseField[str]):
    merge_registry = STRICT_REGISTRY

    def has_data(self) -> bool:
        if self.value.strip() != "":
            return True


@dataclass(kw_only=True, frozen=True)
class Amount:
    value: Decimal | None
    transcription: str | None

    def has_data(self) -> bool:
        if self.value is not None:
            return True
        if self.transcription is not None and self.transcription.strip() != "":
            return True
        return False


@dataclass(kw_only=True, frozen=True)
class Vat:
    amount: Amount | None
    rate: Decimal | None

    def has_data(self) -> bool:
        if self.amount is not None and self.amount.has_data():
            return True
        if self.rate is not None:
            return True
        return False


@dataclass(kw_only=True, frozen=True)
class Payment:
    amount: Amount | None
    vat: Vat
    include_vat: bool | None

    def has_data(self) -> bool:
        if self.amount is not None and self.amount.has_data():
            return True
        if self.vat.has_data():
            return True
        # ignore include_vat data
        return False


@dataclass(kw_only=True, frozen=True)
class TotalAmount:
    total: Payment
    taxes: list[Payment]

    def has_data(self) -> bool:
        if self.total.has_data():
            return True
        if any(payment.has_data() for payment in self.taxes):
            return True
        return False


@dataclass(kw_only=True, frozen=True)
class TotalAmountField(BaseField[TotalAmount]):
    merge_registry = STRICT_REGISTRY

    def has_data(self) -> bool:
        return self.value.has_data()


@dataclass(kw_only=True, frozen=True)
class AdvancePayment:
    percent: Decimal | None
    total: Payment | None
    payments: list[Payment]

    def has_data(self) -> bool:
        if self.percent is not None:
            return True
        if self.total is not None and self.total.has_data():
            return True
        if any(payment.has_data() for payment in self.payments):
            return True
        return False


@dataclass(kw_only=True, frozen=True)
class AdvancePaymentsField(BaseField[list[AdvancePayment]]):
    merge_registry = STRICT_REGISTRY

    def has_data(self) -> bool:
        if any(payment.has_data() for payment in self.value):
            return True
        return False


@dataclass(kw_only=True, frozen=True)
class SpecPosition:
    name: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    total_price: Decimal | None
    unit_of_measurement: str | None

    def has_data(self) -> bool:
        if self.name is not None and self.name.strip() != "":
            return True
        if self.quantity is not None:
            return True
        if self.unit_price is not None:
            return True
        if self.total_price is not None:
            return True
        # ignore unit_of_measurement
        return False


@dataclass(kw_only=True, frozen=True)
class SpecPositionsField(BaseField[list[SpecPosition]]):
    merge_registry = STRICT_REGISTRY

    def has_data(self) -> bool:
        if any(position.has_data() for position in self.value):
            return True
        return False


@dataclass(kw_only=True, frozen=True)
class NomenclatureClassification:
    position: SpecPosition
    articles: list[NomenclatureArticle]


@dataclass(kw_only=True, frozen=True)
class NomenclatureClassificationsField(BaseField[list[NomenclatureClassification]]):
    merge_registry = STRICT_REGISTRY
