from decimal import Decimal
from typing import cast

from app.domain.checks.base import BaseCheck
from app.domain.entities.errors import (
    AmountDiscrepancyError,
    BaseCheckError,
)
from app.domain.entities.single_supplier_fields import (
    AdvancePaymentsField,
    Payment,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .deps import CheckServices, OptionalDep, Requires
from .errors import InsufficientCheckDataError


class CheckTotalAmountsValidation(BaseCheck):
    total_amount_field = Requires(TotalAmountField)
    advance_payments_field = OptionalDep(AdvancePaymentsField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance

    def all_equal(self, values: list[Decimal]) -> list[BaseCheckError]:
        if not values:
            return []
        errors: list[BaseCheckError] = []
        reference_value = values[0]
        for value in values[1:]:
            difference = abs(value - reference_value)
            if difference > self.tolerance:
                errors.append(
                    AmountDiscrepancyError(
                        value=value,
                        reference_value=reference_value,
                        difference=difference,
                    ),
                )
        return errors

    def collect_sums_from_payments(self, payments: list[Payment]) -> Decimal | None:
        total_amount_sum: Decimal | None = None
        for payment in payments:
            if payment.amount is None or payment.amount.value is None:
                continue
            total_amount_sum = (
                total_amount_sum or Decimal("0.00")
            ) + payment.amount.value
        return total_amount_sum

    def collect_total_sum(self, total_amount_field: TotalAmountField) -> list[Decimal]:
        target: list[Decimal] = []
        total_amount_sum = self.collect_sums_from_payments(
            [total_amount_field.value.total],
        )
        if total_amount_sum is not None:
            target.append(total_amount_sum)
        taxes_total_amount_sum = self.collect_sums_from_payments(
            total_amount_field.value.taxes,
        )
        if taxes_total_amount_sum is None:
            return target
        target.append(taxes_total_amount_sum)
        return target

    def collect_advances_sum(
        self,
        advance_payments_field: AdvancePaymentsField,
    ) -> tuple[list[BaseCheckError], Decimal | None]:
        errors: list[BaseCheckError] = []
        advances_sum: Decimal | None = None
        for advance_payment in advance_payments_field.value:
            total_amount = (
                self.collect_sums_from_payments([advance_payment.total])
                if advance_payment.total is not None
                else None
            )
            payments_sum = self.collect_sums_from_payments(advance_payment.payments)

            if total_amount is not None and payments_sum is not None:
                diff = abs(total_amount - payments_sum)
                if diff > self.tolerance:
                    errors.append(
                        AmountDiscrepancyError(
                            reference_value=total_amount,
                            value=payments_sum,
                            difference=diff,
                        )
                    )

            amount = total_amount if total_amount is not None else payments_sum
            if amount is not None:
                advances_sum = (advances_sum or Decimal("0.00")) + amount

        return errors, advances_sum

    async def execute(self, _check_services: CheckServices) -> CheckExecutionResult:
        self.total_amount_field = cast("TotalAmountField", self.total_amount_field)
        self.advance_payments_field = cast(
            "AdvancePaymentsField | None",
            self.advance_payments_field,
        )
        errors: list[BaseCheckError] = []
        amounts_to_compare: list[Decimal] = []
        amounts_to_compare.extend(self.collect_total_sum(self.total_amount_field))
        if self.advance_payments_field is not None:
            adv_errors, advances_sum = self.collect_advances_sum(
                self.advance_payments_field
            )
            errors.extend(adv_errors)
            if advances_sum is not None:
                amounts_to_compare.append(advances_sum)
        if not amounts_to_compare:
            raise InsufficientCheckDataError(
                self.__class__.__name__,
                "no amounts found to compare",
            )
        errors.extend(self.all_equal(amounts_to_compare))

        return self._result(errors)
