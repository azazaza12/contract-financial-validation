from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from functools import reduce
from typing import cast

from app.domain.merge.defaults import STRICT_REGISTRY
from app.domain.merge.handlers import merge_advance_payment, merge_payment
from app.domain.ports.nomenclature_classifier import NomenclatureArticle

from .amount_comparison import (
    AmountDiscrepancy,
    AmountOperand,
    ComparisonResult,
    ComparisonStatus,
    NormalizedAmountDiscrepancy,
    PaymentComparison,
)
from .errors.checks import (
    AmountNotFoundError,
    AmountNotPositiveError,
    BaseCheckError,
    PaymentAmountPercentDiscrepancyError,
    PaymentVatRatesDifferError,
    PositionCostDiscrepancyError,
    PositionsAmountDiscrepancyError,
    UpperBoundAmountError,
    UpperBoundVatAmountError,
    VatAmountCalculationDiscrepancyError,
    VatAmountNotPositiveError,
    VatRateNotPositiveError,
)
from .field import BaseField
from .vat_inclusion import VatInclusion


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

    def validate_positivity(self) -> list[BaseCheckError]:
        if self.value is None:
            return []
        if self.value <= 0:
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

    def validate_positivity(self) -> list[BaseCheckError]:
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


class AmountRelation(StrEnum):
    EXACT = "exact"
    AT_MOST = "at_most"

    def is_satisfied(
        self, actual_value: Decimal, reference_value: Decimal, tolerance: Decimal
    ) -> bool:
        difference = actual_value - reference_value
        match self:
            case AmountRelation.EXACT:
                return abs(difference) <= tolerance
            case AmountRelation.AT_MOST:
                return difference <= tolerance


def _compare_amounts(
    value: Decimal | None,
    reference_value: Decimal | None,
    *,
    tolerance: Decimal,
    relation: AmountRelation,
) -> ComparisonResult[AmountDiscrepancy]:
    if value is None or reference_value is None:
        return ComparisonResult(status=ComparisonStatus.UNKNOWN)
    if relation.is_satisfied(
        actual_value=value,
        reference_value=reference_value,
        tolerance=tolerance,
    ):
        return ComparisonResult(status=ComparisonStatus.OK)
    difference = (
        value - reference_value
        if relation is AmountRelation.AT_MOST
        else abs(reference_value - value)
    )
    return ComparisonResult(
        status=ComparisonStatus.NOT_OK,
        discrepancy=AmountDiscrepancy(
            value=value,
            reference_value=reference_value,
            difference=difference,
        ),
    )


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

    def has_vat_calculation_data(self) -> bool:
        return (
            self.amount_value is not None
            and self.vat_amount_value is not None
            and self.vat_rate is not None
        )

    def validate_positivity(self) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        if self.amount is not None:
            errors.extend(self.amount.validate_positivity())
        if self.vat is not None:
            errors.extend(self.vat.validate_positivity())
        return errors

    def validate_vat_calculation(self, *, tolerance: Decimal) -> list[BaseCheckError]:
        expected = self.expected_vat_amount
        vat_amount = self.vat_amount_value
        if expected is None or vat_amount is None:
            return []
        difference = abs(vat_amount - expected)
        if difference <= tolerance:
            return []
        return [
            VatAmountCalculationDiscrepancyError(
                amount=cast("Decimal", self.amount_value),
                rate=cast("Decimal", self.vat.rate),
                include_vat=self.include_vat is VatInclusion.INCLUDED,
                expected_vat_amount=expected,
                vat_amount=vat_amount,
                difference=difference,
            )
        ]

    def validate_vat_rate(
        self, reference: list[Decimal], *, index: int | None = None
    ) -> list[BaseCheckError]:
        rate = self.vat.rate
        if rate is None or not reference:
            return []
        if len(reference) == 1:
            if rate == reference[0]:
                return []
            return [
                PaymentVatRatesDifferError(
                    index=index, rate_one=reference[0], rate_two=rate
                )
            ]
        if rate in reference:
            return []
        return [PaymentVatRatesDifferError(index=index, rate_one=rate, rate_two=None)]

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
    def amount_operand(self) -> AmountOperand | None:
        value = self.amount_value
        if value is None:
            return None
        return AmountOperand(
            value=value,
            vat_amount=self.vat.amount_value,
            vat_rate=self.vat.rate,
            vat_inclusion=self.include_vat,
        )

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

    def amount_variants(self) -> list[Decimal]:
        values = [
            value
            for value in (self.amount_including_vat, self.amount_excluding_vat)
            if value is not None
        ]
        if values:
            return values
        raw = self.amount_value
        return [raw] if raw is not None else []

    def numeric_moneys(self) -> list[Money]:
        return [
            money
            for money in (self.amount, self.vat.amount)
            if money is not None and money.value is not None
        ]

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

    def amount_as(self, inclusion: VatInclusion) -> Decimal | None:
        if inclusion is VatInclusion.INCLUDED:
            return self.amount_including_vat
        if inclusion is VatInclusion.EXCLUDED:
            return self.amount_excluding_vat
        return self.amount_value

    def __add__(self, other: Payment) -> Payment:
        inclusion = select_common_vat_inclusion([self, other])
        self_amount = self.amount_as(inclusion)
        other_amount = other.amount_as(inclusion)
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

    def normalized_amounts(
        self, other: Payment, *, inclusion: VatInclusion | None = None
    ) -> NormalizedAmounts | None:
        if inclusion is None:
            inclusion = select_common_vat_inclusion([self, other])
        left = self.amount_as(inclusion)
        right = other.amount_as(inclusion)
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
        self,
        reference: Payment,
        *,
        tolerance: Decimal,
        relation: AmountRelation,
        inclusion: VatInclusion | None = None,
    ) -> PaymentComparison:
        normalized = self.normalized_amounts(reference, inclusion=inclusion)
        if normalized is None:
            amount_result = ComparisonResult[NormalizedAmountDiscrepancy](
                status=ComparisonStatus.UNKNOWN
            )
        else:
            amount_comparison = _compare_amounts(
                normalized.left,
                normalized.right,
                tolerance=tolerance,
                relation=relation,
            )
            discrepancy = amount_comparison.discrepancy
            if discrepancy is None:
                amount_result = ComparisonResult[NormalizedAmountDiscrepancy](
                    status=amount_comparison.status
                )
            else:
                amount_result = ComparisonResult(
                    status=ComparisonStatus.NOT_OK,
                    discrepancy=NormalizedAmountDiscrepancy(
                        value=discrepancy.value,
                        reference_value=discrepancy.reference_value,
                        difference=discrepancy.difference,
                        target_inclusion=normalized.inclusion,
                        operands=(cast("AmountOperand", self.amount_operand),),
                        reference_operand=cast(
                            "AmountOperand", reference.amount_operand
                        ),
                    ),
                )
        vat_amount_result = _compare_amounts(
            self.vat.amount_value,
            reference.vat.amount_value,
            tolerance=tolerance,
            relation=relation,
        )
        return PaymentComparison(
            amount=amount_result,
            vat_amount=vat_amount_result,
        )

    def should_merge_economically(
        self, others: Sequence[Payment], *, tolerance: Decimal
    ) -> bool:
        group = [self, *others]
        if len({payment.include_vat for payment in group}) == 1:
            return False
        inclusion = select_common_vat_inclusion(group)
        if inclusion in (VatInclusion.UNSPECIFIED, VatInclusion.MIXED):
            return False
        amounts: list[Decimal] = []
        for payment in group:
            amount = payment.amount_as(inclusion)
            if amount is None:
                return False
            amounts.append(amount)
        return all(abs(amount - amounts[0]) <= tolerance for amount in amounts[1:])


def select_common_vat_inclusion(payments: list[Payment]) -> VatInclusion:
    numbered = [p for p in payments if p.amount_value is not None]
    if not numbered:
        return VatInclusion.UNSPECIFIED
    common = {p.include_vat for p in numbered}
    if VatInclusion.UNSPECIFIED in common:
        return VatInclusion.UNSPECIFIED
    if len(common) == 1:
        return common.pop()
    if all(p.amount_including_vat is not None for p in numbered):
        return VatInclusion.INCLUDED
    if all(p.amount_excluding_vat is not None for p in numbered):
        return VatInclusion.EXCLUDED
    return VatInclusion.MIXED


@dataclass(frozen=True)
class PaymentList:
    _payments: Sequence[Payment]

    def __iter__(self) -> Iterator[Payment]:
        return iter(self._payments)

    def __len__(self) -> int:
        return len(self._payments)

    def __bool__(self) -> bool:
        return bool(self._payments)

    def has_vat_calculation_data(self) -> bool:
        return any(payment.has_vat_calculation_data() for payment in self._payments)

    def validate_positivity(self) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        for payment in self._payments:
            errors.extend(payment.validate_positivity())
        return errors

    def validate_vat_calculation(self, *, tolerance: Decimal) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        for payment in self._payments:
            errors.extend(payment.validate_vat_calculation(tolerance=tolerance))
        return errors

    def numeric_moneys(self) -> list[Money]:
        moneys: list[Money] = []
        for payment in self._payments:
            moneys.extend(payment.numeric_moneys())
        return moneys

    def validate_vat_rate(self, reference: list[Decimal]) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        for i, payment in enumerate(self._payments):
            errors.extend(payment.validate_vat_rate(reference, index=i))
        return errors

    @property
    def vat_rates(self) -> set[Decimal]:
        return {
            payment.vat_rate
            for payment in self._payments
            if payment.vat_rate is not None
        }

    def _summed_in(self, inclusion: VatInclusion) -> Payment | None:
        if not self._payments:
            return None
        amount_value: Decimal | None = None
        for payment in self._payments:
            value = payment.amount_as(inclusion)
            if value is None:
                if payment.amount_value is not None:
                    return None
                continue
            amount_value = value if amount_value is None else amount_value + value
        amount = (
            Money(value=amount_value, transcription=None)
            if amount_value is not None
            else None
        )
        vat = reduce(Vat.__add__, (payment.vat for payment in self._payments))
        result = Payment(amount=amount, vat=vat, include_vat=inclusion)
        return result if result.has_data() else None

    @property
    def summed(self) -> Payment | None:
        if not self._payments:
            return None
        inclusion = select_common_vat_inclusion(list(self._payments))
        return self._summed_in(inclusion)

    def compare_sum(
        self, reference: Payment, *, tolerance: Decimal
    ) -> PaymentComparison:
        if not self._payments:
            return PaymentComparison.unknown()
        inclusion = select_common_vat_inclusion([*self._payments, reference])
        summed = self._summed_in(inclusion)
        if summed is None:
            return PaymentComparison.unknown()
        comparison = summed.compare(
            reference,
            tolerance=tolerance,
            inclusion=inclusion,
            relation=AmountRelation.EXACT,
        )
        discrepancy = comparison.amount.discrepancy
        if discrepancy is None:
            return comparison

        operands = tuple(
            operand
            for payment in self._payments
            if (operand := payment.amount_operand) is not None
        )
        amount_result = replace(
            comparison.amount,
            discrepancy=replace(discrepancy, operands=operands),
        )
        return PaymentComparison(
            amount=amount_result,
            vat_amount=comparison.vat_amount,
        )


@dataclass(kw_only=True, frozen=True)
class TotalAmount:
    total: Payment
    taxes: PaymentList

    def has_data(self) -> bool:
        if self.total.has_data():
            return True
        return bool(any(payment.has_data() for payment in self.taxes))

    def has_vat_calculation_data(self) -> bool:
        return (
            self.total.has_vat_calculation_data()
            or self.taxes.has_vat_calculation_data()
        )

    def validate_positivity(self) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        errors.extend(self.total.validate_positivity())
        errors.extend(self.taxes.validate_positivity())
        return errors

    def validate_presence(self) -> list[BaseCheckError]:
        if self.total.amount_value is None:
            return [AmountNotFoundError()]
        return []

    def validate_vat_calculation(self, *, tolerance: Decimal) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        errors.extend(self.total.validate_vat_calculation(tolerance=tolerance))
        errors.extend(self.taxes.validate_vat_calculation(tolerance=tolerance))
        return errors

    def numeric_moneys(self) -> list[Money]:
        return [*self.total.numeric_moneys(), *self.taxes.numeric_moneys()]


@dataclass(kw_only=True, frozen=True)
class BaseTotalAmountField(BaseField[TotalAmount]):
    merge_registry = STRICT_REGISTRY

    def has_data(self) -> bool:
        return self.value.has_data()

    def validate_positivity(self) -> list[BaseCheckError]:
        return self.value.validate_positivity()

    def numeric_moneys(self) -> list[Money]:
        return self.value.numeric_moneys()


@dataclass(kw_only=True, frozen=True)
class TotalAmountField(BaseTotalAmountField):
    merge_registry = STRICT_REGISTRY

    def validate_presence(self) -> list[BaseCheckError]:
        return self.value.validate_presence()


EMPTY_PAYMENT = Payment(
    amount=None, vat=Vat(amount=None, rate=None), include_vat=VatInclusion.UNSPECIFIED
)


@dataclass(kw_only=True, frozen=True)
class TotalAmountBoundField(BaseTotalAmountField, ABC):
    merge_registry = STRICT_REGISTRY

    @abstractmethod
    def compare(self, actual: Payment, tolerance: Decimal) -> list[BaseCheckError]:
        pass


@dataclass(kw_only=True, frozen=True)
class TotalAmountUpperBoundField(TotalAmountBoundField):
    def compare(self, actual: Payment, tolerance: Decimal) -> list[BaseCheckError]:
        comparison = actual.compare(
            reference=self.value.total,
            relation=AmountRelation.AT_MOST,
            tolerance=tolerance,
        )
        errors: list[BaseCheckError] = []
        if comparison.amount.status is ComparisonStatus.NOT_OK:
            discrepancy = cast(
                "NormalizedAmountDiscrepancy", comparison.amount.discrepancy
            )
            errors.append(
                UpperBoundAmountError(
                    value=discrepancy.value,
                    bound_value=discrepancy.reference_value,
                    violation_value=discrepancy.difference,
                    target_inclusion=discrepancy.target_inclusion,
                    operands=discrepancy.operands,
                    reference_operand=discrepancy.reference_operand,
                )
            )
        if comparison.vat_amount.status is ComparisonStatus.NOT_OK:
            vat_discrepancy = cast(
                "AmountDiscrepancy", comparison.vat_amount.discrepancy
            )
            errors.append(
                UpperBoundVatAmountError(
                    value=vat_discrepancy.value,
                    bound_value=vat_discrepancy.reference_value,
                    violation_value=vat_discrepancy.difference,
                )
            )
        return errors


@dataclass(kw_only=True, frozen=True)
class AdvancePayment(Payment):
    percent: Decimal | None

    def has_data(self) -> bool:
        if self.percent is not None:
            return True
        return super().has_data()

    def has_vat_rate(self) -> bool:
        return self.vat.rate is not None

    def compare_amount_with_percent(
        self, reference: Payment, *, tolerance: Decimal
    ) -> list[BaseCheckError]:
        if self.percent is None:
            return []

        reference_amount = reference.amount_value
        if reference_amount is None:
            return []

        expected = reference.scaled(self.percent)
        normalized = self.normalized_amounts(expected)
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
class AdvancePaymentList(PaymentList):
    _payments: Sequence[AdvancePayment]

    def __iter__(self) -> Iterator[AdvancePayment]:
        return iter(self._payments)

    @property
    def summed(self) -> AdvancePayment | None:
        payment = super().summed

        percents = [ap.percent for ap in self if ap.percent is not None]
        percent_sum = sum(percents, Decimal("0.00")) if percents else None

        total = payment if payment is not None else EMPTY_PAYMENT
        result = AdvancePayment(
            percent=percent_sum,
            amount=total.amount,
            vat=total.vat,
            include_vat=total.include_vat,
        )
        return result if result.has_data() else None


@dataclass(kw_only=True, frozen=True)
class AdvancePaymentsField(BaseField[AdvancePaymentList]):
    merge_registry = STRICT_REGISTRY

    def has_data(self) -> bool:
        return bool(any(payment.has_data() for payment in self.value))

    def validate_positivity(self) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        for advance_payment in self.value:
            errors.extend(advance_payment.validate_positivity())
        return errors

    def numeric_moneys(self) -> list[Money]:
        return self.value.numeric_moneys()


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

    def validate_positivity(self) -> list[BaseCheckError]:
        return [
            AmountNotPositiveError(value=value)
            for value in (self.unit_price, self.total_price)
            if value is not None and value <= 0
        ]

    def validate_cost_calculation(
        self, *, index: int, tolerance: Decimal
    ) -> list[BaseCheckError]:
        if self.total_price is None or self.quantity is None or self.unit_price is None:
            return []
        calculated = self.quantity * self.unit_price
        difference = abs(self.total_price - calculated)
        if difference <= tolerance:
            return []
        return [
            PositionCostDiscrepancyError(
                count=index,
                position_name=self.name,
                quantity=self.quantity,
                unit_price=self.unit_price,
                cost=self.total_price,
                calculated_cost=calculated,
                difference_sum=difference,
            )
        ]


@dataclass(frozen=True)
class Specification:
    _positions: list[SpecPosition]

    def __iter__(self) -> Iterator[SpecPosition]:
        return iter(self._positions)

    def __len__(self) -> int:
        return len(self._positions)

    def __bool__(self) -> bool:
        return bool(self._positions)

    def has_position_totals(self) -> bool:
        return any(position.total_price is not None for position in self._positions)

    @property
    def total_price_sum(self) -> Decimal | None:
        total: Decimal | None = None
        for position in self._positions:
            if position.total_price is None:
                continue
            total = (total or Decimal("0.00")) + position.total_price
        return total

    def validate_cost_calculation(self, *, tolerance: Decimal) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        for index, position in enumerate(self._positions, start=1):
            errors.extend(
                position.validate_cost_calculation(index=index, tolerance=tolerance)
            )
        return errors

    def compare_total_with(
        self, total_payment: Payment, *, tolerance: Decimal
    ) -> list[BaseCheckError]:
        positions_total = self.total_price_sum
        if positions_total is None:
            return []

        candidates = total_payment.amount_variants()
        if not candidates:
            return []

        closest = min(
            candidates, key=lambda candidate: abs(positions_total - candidate)
        )
        difference = abs(positions_total - closest)
        if difference <= tolerance:
            return []
        return [
            PositionsAmountDiscrepancyError(
                reference_value=closest,
                value=positions_total,
                difference=difference,
            )
        ]


@dataclass(kw_only=True, frozen=True)
class SpecPositionsField(BaseField[Specification]):
    merge_registry = STRICT_REGISTRY

    def has_data(self) -> bool:
        return bool(any(position.has_data() for position in self.value))

    def validate_positivity(self) -> list[BaseCheckError]:
        errors: list[BaseCheckError] = []
        for position in self.value:
            errors.extend(position.validate_positivity())
        return errors


@dataclass(kw_only=True, frozen=True)
class NomenclatureClassification:
    position: SpecPosition
    articles: list[NomenclatureArticle]


@dataclass(kw_only=True, frozen=True)
class NomenclatureClassificationsField(BaseField[list[NomenclatureClassification]]):
    merge_registry = STRICT_REGISTRY


STRICT_REGISTRY.register_type(Payment, merge_payment)
STRICT_REGISTRY.register_type(AdvancePayment, merge_advance_payment)
