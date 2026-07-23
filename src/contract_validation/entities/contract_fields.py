from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.domain.merge.defaults import STRICT_REGISTRY
from app.domain.merge.handlers import merge_payment
from app.domain.ports.nomenclature_classifier import NomenclatureArticle

from .field import BaseField


class Basis(StrEnum):
    INCLUDING_VAT = "including_vat"
    EXCLUDING_VAT = "excluding_vat"
    RAW = "raw"


class VatInclusion(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"
    UNSPECIFIED = "unspecified"
    MIXED = "mixed"


class DocumentObjectField(BaseField[str]):
    merge_registry = STRICT_REGISTRY

    def has_data(self) -> bool:
        return self.value.strip() != ""


@dataclass(kw_only=True, frozen=True)
class Money:
    value: Decimal | None
    transcription: str | None

    def has_data(self) -> bool:
        if self.value is not None:
            return True
        return bool(self.transcription is not None and self.transcription.strip() != "")


@dataclass(kw_only=True, frozen=True)
class Vat:
    amount: Money | None
    rate: Decimal | None

    @property
    def amount_value(self) -> Decimal | None:
        return self.amount.value if self.amount is not None else None

    def has_data(self) -> bool:
        if self.amount is not None and self.amount.has_data():
            return True
        return self.rate is not None


@dataclass(kw_only=True, frozen=True)
class Payment:
    amount: Money | None
    vat: Vat
    include_vat: VatInclusion

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
        return self.vat.amount_value

    @property
    def vat_rate(self) -> Decimal | None:
        return self.vat.rate

    @property
    def expected_vat_amount(self) -> Decimal | None:
        amount = self.amount_value
        rate = self.vat.rate
        if (
            amount is None
            or rate is None
            or self.include_vat is VatInclusion.UNSPECIFIED
        ):
            return None
        if self.include_vat is VatInclusion.INCLUDED:
            denominator = 100 + rate
            if denominator <= 0:
                return None
            return amount * rate / denominator
        return amount * rate / 100

    @property
    def amount_excluding_vat(self) -> Decimal | None:
        stated = self.amount_value
        if stated is None or self.include_vat is VatInclusion.UNSPECIFIED:
            return None
        if self.include_vat is VatInclusion.EXCLUDED:
            return stated
        if self.vat.rate is None:
            return None
        gross_percent = Decimal(100) + self.vat.rate
        if gross_percent <= 0:
            return None
        return stated * Decimal(100) / gross_percent

    @property
    def amount_including_vat(self) -> Decimal | None:
        stated = self.amount_value
        if stated is None or self.include_vat is VatInclusion.UNSPECIFIED:
            return None
        if self.include_vat is VatInclusion.INCLUDED:
            return stated
        if self.vat.rate is None:
            return None
        return stated * (Decimal(100) + self.vat.rate) / Decimal(100)

    def amount_in_basis(self, basis: Basis) -> Decimal | None:
        if basis is Basis.INCLUDING_VAT:
            return self.amount_including_vat
        if basis is Basis.EXCLUDING_VAT:
            return self.amount_excluding_vat
        return self.amount_value

    def should_merge_economically(
        self, others: list[Payment], *, tolerance: Decimal
    ) -> bool:
        group = [self, *others]
        basis = select_basis(group)
        if basis is Basis.RAW:
            return False
        amounts: list[Decimal] = []
        for payment in group:
            amount = payment.amount_in_basis(basis)
            if amount is None:
                return False
            amounts.append(amount)
        return all(abs(amount - amounts[0]) <= tolerance for amount in amounts[1:])


def select_basis(payments: list[Payment]) -> Basis:
    numbered = [p for p in payments if p.amount_value is not None]
    if not numbered:
        return Basis.RAW
    if len({p.include_vat for p in numbered}) == 1:
        return Basis.RAW
    if all(p.amount_including_vat is not None for p in numbered):
        return Basis.INCLUDING_VAT
    if all(p.amount_excluding_vat is not None for p in numbered):
        return Basis.EXCLUDING_VAT
    return Basis.RAW


@dataclass(frozen=True)
class PaymentList:
    _payments: list[Payment]

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

    def amount_in_basis(self, basis: Basis) -> Decimal | None:
        total: Decimal | None = None
        for payment in self._payments:
            value = payment.amount_in_basis(basis)
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
    def _include_vat(self) -> VatInclusion:
        values = {
            payment.include_vat
            for payment in self._payments
            if payment.include_vat is not VatInclusion.UNSPECIFIED
        }

        if not values:
            return VatInclusion.UNSPECIFIED
        if len(values) == 1:
            return values.pop()
        return VatInclusion.MIXED

    @property
    def combined(self) -> Payment | None:
        amount_value = self.amount_value
        vat_amount_value = self._vat_amount_value
        rate = self._vat_rate
        if amount_value is None and vat_amount_value is None and rate is None:
            return None
        amount = (
            Money(value=amount_value, transcription=None)
            if amount_value is not None
            else None
        )
        vat_amount = (
            Money(value=vat_amount_value, transcription=None)
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
    taxes: PaymentList

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

    def amount_in_basis(self, basis: Basis) -> Decimal | None:
        if self.total is not None:
            total = self.total.amount_in_basis(basis)
            if total is not None:
                return total
        return self.payment_lines.amount_in_basis(basis)


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
