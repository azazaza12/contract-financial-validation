from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal

from app.domain.merge.defaults import STRICT_REGISTRY
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
    def amount_value(self) -> Decimal | None:
        if self.amount is None:
            return None
        return self.amount.value

    @property
    def vat_amount_value(self) -> Decimal | None:
        if self.vat.amount is None:
            return None
        return self.vat.amount.value

    @property
    def vat_rate(self) -> Decimal | None:
        return self.vat.rate

    @property
    def expected_vat_amount(self) -> Decimal | None:
        amount = self.amount_value
        rate = self.vat.rate
        if amount is None or rate is None:
            return None
        # TODO: подумать над include_vat is None
        if self.include_vat:
            denominator = 100 + rate
            if denominator == 0:
                return None
            return amount * rate / denominator
        return amount * rate / 100


class PaymentList:
    def __init__(self, payments: list[Payment]) -> None:
        self._payments = payments

    def __iter__(self) -> Iterator[Payment]:
        return iter(self._payments)

    def __len__(self) -> int:
        return len(self._payments)

    def __bool__(self) -> bool:
        return bool(self._payments)

    @property
    def amount_value(self) -> Decimal | None:
        total: Decimal | None = None
        for payment in self._payments:
            value = payment.amount_value
            if value is None:
                continue
            total = (total or Decimal("0.00")) + value
        return total

    @property
    def _vat_amount_value(self) -> Decimal | None:
        total: Decimal | None = None
        for payment in self._payments:
            value = payment.vat_amount_value
            if value is None:
                continue
            total = (total or Decimal("0.00")) + value
        return total

    @property
    def vat_rates(self) -> set[Decimal]:
        return {
            payment.vat_rate
            for payment in self._payments
            if payment.vat_rate is not None
        }

    @property
    def _vat_rate(self) -> Decimal | None:
        rates = self.vat_rates
        if len(rates) == 1:
            return next(iter(rates))
        return None

    @property
    def _include_vat(self) -> bool | None:
        values = {
            payment.include_vat
            for payment in self._payments
            if payment.include_vat is not None
        }
        if len(values) == 1:
            return next(iter(values))
        return None

    @property
    def combined(self) -> Payment | None:
        amount_value = self.amount_value
        vat_amount_value = self._vat_amount_value
        rate = self._vat_rate
        if amount_value is None and vat_amount_value is None and rate is None:
            return None
        amount = (
            Amount(value=amount_value, transcription=None)
            if amount_value is not None
            else None
        )
        vat_amount = (
            Amount(value=vat_amount_value, transcription=None)
            if vat_amount_value is not None
            else None
        )
        return Payment(
            amount=amount,
            vat=Vat(amount=vat_amount, rate=rate),
            include_vat=self._include_vat,
        )


@dataclass(kw_only=True, frozen=True)
class TotalAmount:
    total: Payment
    taxes: list[Payment]

    def has_data(self) -> bool:
        if self.total.has_data():
            return True
        return bool(any(payment.has_data() for payment in self.taxes))

    @property
    def tax_payments(self) -> PaymentList:
        return PaymentList(self.taxes)


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

    @property
    def payment_lines(self) -> PaymentList:
        return PaymentList(self.payments)

    @property
    def resolved_total(self) -> Payment | None:
        base = self.total if self.total is not None else self.payment_lines.combined
        if base is None:
            return None
        if base.amount_value is not None:
            return base
        fallback = self.payment_lines.combined
        return fallback if fallback is not None else base


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
