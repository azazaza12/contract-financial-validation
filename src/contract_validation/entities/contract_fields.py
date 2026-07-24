from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from functools import reduce

from app.domain.merge.defaults import STRICT_REGISTRY
from app.domain.merge.handlers import merge_payment
from app.domain.ports.nomenclature_classifier import NomenclatureArticle

from .errors.base import BaseContractError
from .errors.checks import (
    AmountNotPositiveError,
    VatRateNotPositiveError,
)
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


class MoneyValidationMode(StrEnum):
    POSITIVE = "positive"
    NON_NEGATIVE = "non_negative"


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

    def validate(
        self, mode: MoneyValidationMode = MoneyValidationMode.POSITIVE
    ) -> list[BaseContractError]:
        if self.value is None:
            return []

        if self.value < 0:
            return [AmountNotPositiveError(value=self.value)]

        if mode is MoneyValidationMode.POSITIVE and self.value == Decimal(0):
            return [AmountNotPositiveError(value=self.value)]
        return []

    def __add__(self, other: Money) -> Money:
        if self.value is None:
            value = other.value
        elif other.value is None:
            value = self.value
        else:
            value = self.value + other.value
        return Money(value=value, transcription=None)

    def __sub__(self, other: Money) -> Money:
        if self.value is None or other.value is None:
            value = None
        else:
            value = self.value - other.value
        return Money(value=value, transcription=None)


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

    def validate(self) -> list[BaseContractError]:
        errors: list[BaseContractError] = []
        if self.rate is not None and self.rate < 0:
            errors.append(VatRateNotPositiveError(value=self.rate))
        if self.amount is not None:
            errors.extend(self.amount.validate(MoneyValidationMode.NON_NEGATIVE))
        return errors

    def __add__(self, other: Vat) -> Vat:
        if self.amount is None:
            amount = other.amount
        elif other.amount is None:
            amount = self.amount
        else:
            amount = self.amount + other.amount
        rate = self.rate if self.rate is not None and self.rate == other.rate else None
        return Vat(amount=amount, rate=rate)

    def __sub__(self, other: Vat) -> Vat:
        if self.amount is None or other.amount is None:
            amount = None
        else:
            amount = self.amount - other.amount
        return Vat(amount=amount, rate=None)


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

    def validate(self) -> list[BaseContractError]:
        errors = []
        if self.amount is not None:
            errors.extend(self.amount.validate())
        if self.vat is not None:
            errors.extend(self.vat.validate())
        return errors

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
        if self.vat.rate is not None:
            gross_percent = Decimal(100) + self.vat.rate
            if gross_percent > 0:
                return stated * Decimal(100) / gross_percent
        vat_amount = self.vat.amount_value
        if vat_amount is not None:
            return stated - vat_amount
        return None

    @property
    def amount_including_vat(self) -> Decimal | None:
        stated = self.amount_value
        if stated is None or self.include_vat is VatInclusion.UNSPECIFIED:
            return None
        if self.include_vat is VatInclusion.INCLUDED:
            return stated
        if self.vat.rate is not None:
            return stated * (Decimal(100) + self.vat.rate) / Decimal(100)
        vat_amount = self.vat.amount_value
        if vat_amount is not None:
            return stated + vat_amount
        return None

    def amount_in_basis(self, basis: Basis) -> Decimal | None:
        if basis is Basis.INCLUDING_VAT:
            return self.amount_including_vat
        if basis is Basis.EXCLUDING_VAT:
            return self.amount_excluding_vat
        return self.amount_value

    def _amount_as(self, inclusion: VatInclusion) -> Decimal | None:
        if inclusion is VatInclusion.INCLUDED:
            return self.amount_including_vat
        if inclusion is VatInclusion.EXCLUDED:
            return self.amount_excluding_vat
        return self.amount_value

    def __add__(self, other: Payment) -> Payment:
        inclusion = select_common_vat_inclusion([self, other])
        self_amount = self._amount_as(inclusion)
        other_amount = other._amount_as(inclusion)
        if self_amount is None:
            amount_value = other_amount
        elif other_amount is None:
            amount_value = self_amount
        else:
            amount_value = self_amount + other_amount
        amount = (
            Money(value=amount_value, transcription=None)
            if amount_value is not None
            else None
        )
        return Payment(
            amount=amount,
            vat=self.vat + other.vat,
            include_vat=inclusion,
        )

    def __sub__(self, other: Payment) -> Payment:
        inclusion = select_common_vat_inclusion([self, other])
        self_amount = self._amount_as(inclusion)
        other_amount = other._amount_as(inclusion)
        amount_value = (
            self_amount - other_amount
            if self_amount is not None and other_amount is not None
            else None
        )
        amount = (
            Money(value=amount_value, transcription=None)
            if amount_value is not None
            else None
        )
        return Payment(
            amount=amount,
            vat=self.vat - other.vat,
            include_vat=inclusion,
        )

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


def select_common_vat_inclusion(payments: list[Payment]) -> VatInclusion:
    numbered = [p for p in payments if p.amount_value is not None]
    if not numbered:
        return VatInclusion.UNSPECIFIED
    common = {p.include_vat for p in numbered}
    if len(common) == 1:
        return common.pop()
    if all(p.amount_including_vat is not None for p in numbered):
        return VatInclusion.INCLUDED
    if all(p.amount_excluding_vat is not None for p in numbered):
        return VatInclusion.EXCLUDED
    return VatInclusion.MIXED


@dataclass(frozen=True)
class PaymentList:
    _payments: list[Payment]

    def __iter__(self) -> Iterator[Payment]:
        return iter(self._payments)

    def __len__(self) -> int:
        return len(self._payments)

    def __bool__(self) -> bool:
        return bool(self._payments)

    def validate(self) -> list[BaseContractError]:
        errors = []
        for payment in self._payments:
            errors.extend(payment.validate())
        return errors

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
    def vat_rates(self) -> set[Decimal]:
        return {
            payment.vat_rate
            for payment in self._payments
            if payment.vat_rate is not None
        }

    @property
    def summed(self) -> Payment | None:
        if not self._payments:
            return None
        result = reduce(Payment.__add__, self._payments)
        return result if result.has_data() else None


@dataclass(kw_only=True, frozen=True)
class TotalAmount:
    total: Payment
    taxes: PaymentList

    def has_data(self) -> bool:
        if self.total.has_data():
            return True
        return bool(any(payment.has_data() for payment in self.taxes))

    def validate(self) -> list[BaseContractError]:
        errors = []
        errors.extend(self.total.validate())
        errors.extend(self.taxes.validate())
        return errors

    def get_moneys(self) -> list[Money]:
        moneys: list[Money] = []
        total_money = self.total.amount
        if total_money is not None:
            moneys.append(total_money)
        moneys.extend(ta.amount for ta in self.taxes if ta.amount is not None)
        return moneys


@dataclass(kw_only=True, frozen=True)
class TotalAmountField(BaseField[TotalAmount]):
    merge_registry = STRICT_REGISTRY

    def has_data(self) -> bool:
        return self.value.has_data()

    def validate(self) -> list[BaseContractError]:
        return self.value.validate()


@dataclass(kw_only=True, frozen=True)
class AdvancePayment:
    percent: Decimal | None
    total: Payment | None
    payments: PaymentList

    def has_data(self) -> bool:
        if self.percent is not None:
            return True
        if self.total is not None and self.total.has_data():
            return True
        return bool(any(payment.has_data() for payment in self.payments))

    def amount_in_basis(self, basis: Basis) -> Decimal | None:
        if self.total is not None:
            total = self.total.amount_in_basis(basis)
            if total is not None:
                return total
        return self.payments.amount_in_basis(basis)


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
