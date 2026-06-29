from dataclasses import dataclass
from decimal import Decimal

from app.domain.constants import AMOUNT_TOLERANCE
from app.domain.merge.defaults import STRICT_REGISTRY
from app.domain.merge.handlers import merge_payment
from app.domain.ports.nomenclature_classifier import NomenclatureArticle

from .field import BaseField


class DocumentObjectField(BaseField[str]):
    merge_registry = STRICT_REGISTRY

    def has_data(self) -> bool:
        return self.value.strip() != ""


@dataclass(kw_only=True, frozen=True)
class Amount:
    value: Decimal | None
    transcription: str | None

    def has_data(self) -> bool:
        if self.value is not None:
            return True
        return bool(self.transcription is not None and self.transcription.strip() != "")


@dataclass(kw_only=True, frozen=True)
class Vat:
    amount: Amount | None
    rate: Decimal | None

    @property
    def stated_amount(self) -> Decimal | None:
        return self.amount.value if self.amount is not None else None

    def has_data(self) -> bool:
        if self.amount is not None and self.amount.has_data():
            return True
        return self.rate is not None


@dataclass(kw_only=True, frozen=True)
class Payment:
    amount: Amount | None
    vat: Vat
    include_vat: bool | None

    def has_data(self) -> bool:
        # ignore include_vat data
        return (
            self.amount is not None and self.amount.has_data()
        ) or self.vat.has_data()

    @property
    def stated_amount(self) -> Decimal | None:
        return self.amount.value if self.amount is not None else None

    @property
    def calculated_vat_amount(self) -> Decimal | None:
        stated = self.stated_amount
        if stated is None or self.vat.rate is None or self.include_vat is None:
            return None
        if self.include_vat:
            return stated * self.vat.rate / (Decimal(100) + self.vat.rate)
        return stated * self.vat.rate / Decimal(100)

    @property
    def amount_excluding_vat(self) -> Decimal | None:
        stated = self.stated_amount
        if stated is None or self.include_vat is None:
            return None
        if not self.include_vat:
            return stated
        if self.vat.rate is None:
            return None
        return stated * Decimal(100) / (Decimal(100) + self.vat.rate)

    @property
    def amount_including_vat(self) -> Decimal | None:
        stated = self.stated_amount
        if stated is None or self.include_vat is None:
            return None
        if self.include_vat:
            return stated
        if self.vat.rate is None:
            return None
        return stated * (Decimal(100) + self.vat.rate) / Decimal(100)

    @property
    def amount_including_vat_or_stated(self) -> Decimal | None:
        including_vat = self.amount_including_vat
        if including_vat is not None:
            return including_vat
        return self.stated_amount

    @staticmethod
    def _differ_beyond_tolerance(a: Decimal | None, b: Decimal | None) -> bool:
        return a is not None and b is not None and abs(a - b) > AMOUNT_TOLERANCE

    def is_equivalent_to(self, other: Payment) -> bool:
        self_net = self.amount_excluding_vat
        other_net = other.amount_excluding_vat
        if self_net is None or other_net is None:
            return False
        return not self._differ_beyond_tolerance(self_net, other_net)


@dataclass(kw_only=True, frozen=True)
class TotalAmount:
    total: Payment
    taxes: list[Payment]

    def has_data(self) -> bool:
        if self.total.has_data():
            return True
        return bool(any(payment.has_data() for payment in self.taxes))


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
        return bool(any(payment.has_data() for payment in self.payments))


@dataclass(kw_only=True, frozen=True)
class AdvancePaymentsField(BaseField[list[AdvancePayment]]):
    merge_registry = STRICT_REGISTRY

    def has_data(self) -> bool:
        return bool(any(payment.has_data() for payment in self.value))


@dataclass(kw_only=True, frozen=True)
class SpecPosition:
    name: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    total_price: Decimal | None
    unit_of_measurement: str | None

    def has_data(self) -> bool:
        # ignore unit_of_measurement
        return (
            (self.name is not None and self.name.strip() != "")
            or self.quantity is not None
            or self.unit_price is not None
            or self.total_price is not None
        )


@dataclass(kw_only=True, frozen=True)
class SpecPositionsField(BaseField[list[SpecPosition]]):
    merge_registry = STRICT_REGISTRY

    def has_data(self) -> bool:
        return bool(any(position.has_data() for position in self.value))


@dataclass(kw_only=True, frozen=True)
class NomenclatureClassification:
    position: SpecPosition
    articles: list[NomenclatureArticle]


@dataclass(kw_only=True, frozen=True)
class NomenclatureClassificationsField(BaseField[list[NomenclatureClassification]]):
    merge_registry = STRICT_REGISTRY


STRICT_REGISTRY.register_type(Payment, merge_payment)
