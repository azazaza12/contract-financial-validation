from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from functools import reduce

from app.domain.merge.defaults import STRICT_REGISTRY
from app.domain.merge.handlers import merge_payment
from app.domain.ports.nomenclature_classifier import NomenclatureArticle

from .errors.checks import (
    AmountDiscrepancyError,
    AmountNotPositiveError,
    BaseCheckError,
    PaymentAmountPercentDiscrepancyError,
    VatAmountCalculationDiscrepancyError,
    VatAmountDiscrepancyError,
    VatAmountNotPositiveError,
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
    ) -> list[BaseCheckError]:
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

    def validate(self) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        if self.rate is not None and self.rate < 0:
            errors.append(VatRateNotPositiveError(value=self.rate))
        amount = self.amount_value
        if amount is not None and amount < 0:
            errors.append(VatAmountNotPositiveError(value=amount))
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


@dataclass(frozen=True, kw_only=True)
class NormalizedAmounts:
    left: Decimal
    right: Decimal
    inclusion: VatInclusion

    @property
    def difference(self) -> Decimal:
        return self.left - self.right


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

    def has_amounts(self) -> bool:
        return self.amount_value is not None or self.vat_amount_value is not None

    def has_vat_calculation_data(self) -> bool:
        return (
            self.amount_value is not None
            and self.vat_amount_value is not None
            and self.vat_rate is not None
        )

    def validate(self) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        if self.amount is not None:
            errors.extend(self.amount.validate())
        if self.vat is not None:
            errors.extend(self.vat.validate())
        return errors

    def vat_calculation_error(self, *, tolerance: Decimal) -> list[BaseCheckError]:
        expected = self.expected_vat_amount
        vat_amount = self.vat_amount_value
        if expected is None or vat_amount is None:
            return []
        difference = abs(vat_amount - expected)
        if difference <= tolerance:
            return []
        return [
            VatAmountCalculationDiscrepancyError(
                expected_vat_amount=expected,
                vat_amount=vat_amount,
                difference=difference,
            )
        ]

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
            or self.include_vat is VatInclusion.MIXED
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

    def scaled(self, percent: Decimal) -> Payment:
        factor = percent / Decimal("100.00")
        amount = (
            Money(value=self.amount_value * factor, transcription=None)
            if self.amount_value is not None
            else None
        )
        vat_amount = (
            Money(value=self.vat_amount_value * factor, transcription=None)
            if self.vat_amount_value is not None
            else None
        )
        return Payment(
            amount=amount,
            vat=Vat(amount=vat_amount, rate=self.vat.rate),
            include_vat=self.include_vat,
        )

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

    def normalized_amounts(self, other: Payment) -> NormalizedAmounts | None:
        inclusion = select_common_vat_inclusion([self, other])
        left = self._amount_as(inclusion)
        right = other._amount_as(inclusion)
        if left is None or right is None:
            return None
        return NormalizedAmounts(left=left, right=right, inclusion=inclusion)

    def __sub__(self, other: Payment) -> Payment:
        normalized = self.normalized_amounts(other)
        if normalized is None:
            return Payment(
                amount=None,
                vat=self.vat - other.vat,
                include_vat=select_common_vat_inclusion([self, other]),
            )
        difference = normalized.difference
        amount = Money(value=difference, transcription=None)
        return Payment(
            amount=amount,
            vat=self.vat - other.vat,
            include_vat=normalized.inclusion,
        )

    def compare(
        self, reference: Payment, *, tolerance: Decimal
    ) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        normalized = self.normalized_amounts(reference)
        value_vat_amount = self.vat.amount_value
        reference_vat_amount = reference.vat.amount_value
        if normalized is not None:
            amount_difference = abs(normalized.difference)
            if amount_difference > tolerance:
                errors.append(
                    AmountDiscrepancyError(
                        value=normalized.left,
                        reference_value=normalized.right,
                        difference=amount_difference,
                    )
                )
        if value_vat_amount is not None and reference_vat_amount is not None:
            vat_amount_difference = abs(reference_vat_amount - value_vat_amount)
            if vat_amount_difference > tolerance:
                errors.append(
                    VatAmountDiscrepancyError(
                        value=value_vat_amount,
                        reference_value=reference_vat_amount,
                        difference=vat_amount_difference,
                    )
                )
        return errors

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

    def has_amounts(self) -> bool:
        return any(payment.has_amounts() for payment in self._payments)

    def has_vat_calculation_data(self) -> bool:
        return any(payment.has_vat_calculation_data() for payment in self._payments)

    def validate(self) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        for payment in self._payments:
            errors.extend(payment.validate())
        return errors

    def validate_vat_calculation(self, *, tolerance: Decimal) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        for payment in self._payments:
            errors.extend(payment.vat_calculation_error(tolerance=tolerance))
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

    def has_amounts(self) -> bool:
        return self.total.has_amounts() or self.taxes.has_amounts()

    def has_vat_calculation_data(self) -> bool:
        return (
            self.total.has_vat_calculation_data()
            or self.taxes.has_vat_calculation_data()
        )

    def validate(self) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        errors.extend(self.total.validate())
        errors.extend(self.taxes.validate())
        return errors

    def validate_vat_calculation(self, *, tolerance: Decimal) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        errors.extend(self.total.vat_calculation_error(tolerance=tolerance))
        errors.extend(self.taxes.validate_vat_calculation(tolerance=tolerance))
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

    def has_amounts(self) -> bool:
        return self.value.has_amounts()

    def validate(self) -> list[BaseCheckError]:
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

    def has_amounts(self) -> bool:
        return (
            self.total is not None and self.total.has_amounts()
        ) or self.payments.has_amounts()

    def has_vat_calculation_data(self) -> bool:
        return (
            self.total is not None and self.total.has_vat_calculation_data()
        ) or self.payments.has_vat_calculation_data()

    def validate(self) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        if self.total is not None:
            errors.extend(self.total.validate())
        errors.extend(self.payments.validate())
        return errors

    def validate_vat_calculation(self, *, tolerance: Decimal) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        if self.total is not None:
            errors.extend(self.total.vat_calculation_error(tolerance=tolerance))
        errors.extend(self.payments.validate_vat_calculation(tolerance=tolerance))
        return errors

    @property
    def resolved(self) -> Payment | None:
        payments_sum = self.payments.summed
        if self.total is None:
            return payments_sum
        if payments_sum is None:
            return self.total if self.total.has_data() else None

        total = self.total
        amount = total.amount if total.amount_value is not None else payments_sum.amount
        vat_amount = (
            total.vat.amount
            if total.vat_amount_value is not None
            else payments_sum.vat.amount
        )
        vat_rate = (
            total.vat.rate if total.vat.rate is not None else payments_sum.vat.rate
        )
        include_vat = (
            total.include_vat
            if total.amount_value is not None
            else payments_sum.include_vat
        )
        return Payment(
            amount=amount,
            vat=Vat(amount=vat_amount, rate=vat_rate),
            include_vat=include_vat,
        )

    def amount_in_basis(self, basis: Basis) -> Decimal | None:
        if self.total is not None:
            total = self.total.amount_in_basis(basis)
            if total is not None:
                return total
        return self.payments.amount_in_basis(basis)

    def compare_payments_with_total(
        self, *, tolerance: Decimal
    ) -> list[BaseCheckError]:
        if self.total is None:
            return []

        payments_sum = self.payments.summed
        if payments_sum is None:
            return []

        return payments_sum.compare(self.total, tolerance=tolerance)

    def compare_amount_with_percent(
        self, reference: Payment, *, tolerance: Decimal
    ) -> list[BaseCheckError]:
        if self.percent is None:
            return []

        reference_amount = reference.amount_value
        if reference_amount is None:
            return []

        line_payment = self.resolved
        if line_payment is None:
            return []

        expected = reference.scaled(self.percent)
        normalized = line_payment.normalized_amounts(expected)
        if normalized is None:
            return []

        if abs(normalized.difference) <= tolerance:
            return []

        return [
            PaymentAmountPercentDiscrepancyError(
                amount=normalized.left,
                expected_amount=normalized.right,
                percent=self.percent,
                contract_total_amount=reference_amount,
            )
        ]


@dataclass(frozen=True)
class AdvancePaymentList:
    _advance_payments: list[AdvancePayment]

    def __iter__(self) -> Iterator[AdvancePayment]:
        return iter(self._advance_payments)

    def __len__(self) -> int:
        return len(self._advance_payments)

    def __bool__(self) -> bool:
        return bool(self._advance_payments)

    def has_vat_calculation_data(self) -> bool:
        return any(ap.has_vat_calculation_data() for ap in self._advance_payments)

    def validate_vat_calculation(self, *, tolerance: Decimal) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        for ap in self._advance_payments:
            errors.extend(ap.validate_vat_calculation(tolerance=tolerance))
        return errors

    @property
    def summed(self) -> AdvancePayment | None:
        resolved = [
            ap.resolved for ap in self._advance_payments if ap.resolved is not None
        ]
        payment = PaymentList(resolved).summed

        percents = [
            ap.percent for ap in self._advance_payments if ap.percent is not None
        ]
        percent_sum = sum(percents, Decimal("0.00")) if percents else None

        result = AdvancePayment(
            percent=percent_sum, total=payment, payments=PaymentList([])
        )
        return result if result.has_data() else None


@dataclass(kw_only=True, frozen=True)
class AdvancePaymentsField(BaseField[list[AdvancePayment]]):
    merge_registry = STRICT_REGISTRY

    def has_data(self) -> bool:
        return bool(any(payment.has_data() for payment in self.value))

    def has_amounts(self) -> bool:
        return any(payment.has_amounts() for payment in self.value)

    def validate(self) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        for advance_payment in self.value:
            errors.extend(advance_payment.validate())
        return errors


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

    def validate(self) -> list[BaseCheckError]:
        return [
            AmountNotPositiveError(value=value)
            for value in (self.unit_price, self.total_price)
            if value is not None and value <= 0
        ]


@dataclass(kw_only=True, frozen=True)
class SpecPositionsField(BaseField[list[SpecPosition]]):
    merge_registry = STRICT_REGISTRY

    def has_data(self) -> bool:
        return bool(any(position.has_data() for position in self.value))

    def validate(self) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        for position in self.value:
            errors.extend(position.validate())
        return errors


@dataclass(kw_only=True, frozen=True)
class NomenclatureClassification:
    position: SpecPosition
    articles: list[NomenclatureArticle]


@dataclass(kw_only=True, frozen=True)
class NomenclatureClassificationsField(BaseField[list[NomenclatureClassification]]):
    merge_registry = STRICT_REGISTRY


STRICT_REGISTRY.register_type(Payment, merge_payment)
