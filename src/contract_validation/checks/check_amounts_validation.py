import logging
from decimal import Decimal

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


logger = logging.getLogger(__name__)


class CheckTotalAmountsValidation(BaseCheck):
    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance

    def all_equal(self, values: list[Decimal], errors: list[BaseCheckError]) -> None:
        if not values:
            return
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

    def collect_sums_from_payments(self, payments: list[Payment]) -> Decimal | None:
        total_amount_sum = Decimal("0.00")
        has_any = False
        for payment in payments:
            if payment.amount is None:
                continue
            total_amount_sum += payment.amount.value
            has_any = True
        if not has_any:
            return None
        return total_amount_sum

    def collect_total_sum(self, total_amount_field: TotalAmountField) -> list[Decimal]:
        target: list[Decimal] = []
        total_amount_sum = self.collect_sums_from_payments(
            [total_amount_field.value.total],
        )
        if total_amount_sum is not None:
            target.append(total_amount_sum)
        if total_amount_field.value.taxes is None:
            return target

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
        errors: list[BaseCheckError],
    ) -> list[Decimal]:
        target: list[Decimal] = []
        total_amount_sum = Decimal("0.00")
        total_payments_sum = Decimal("0.00")
        has_any = False
        for advance_payment in advance_payments_field.value:
            total_amount = None
            adv_amount_sum = None
            if advance_payment.total is not None:
                total_amount = self.collect_sums_from_payments([advance_payment.total])
                if total_amount is not None:
                    total_amount_sum += total_amount
                    has_any = True
            if advance_payment.payments is not None:
                adv_amount_sum = self.collect_sums_from_payments(
                    advance_payment.payments,
                )
                if adv_amount_sum is not None:
                    total_payments_sum += adv_amount_sum
                    has_any = True
            if total_amount is None or adv_amount_sum is None:
                continue

            diff = abs(total_amount - adv_amount_sum)
            if diff <= self.tolerance:
                continue

            errors.append(
                AmountDiscrepancyError(
                    reference_value=total_amount,
                    value=adv_amount_sum,
                    difference=diff,
                ),
            )
        if not has_any:
            return target
        target.append(total_amount_sum)
        target.append(total_payments_sum)
        return target

    async def execute(
        self,
        total_amount_field: TotalAmountField,
        advance_payments_field: AdvancePaymentsField | None,
    ) -> CheckExecutionResult:

        errors: list[BaseCheckError] = []
        amounts_to_compare: list[Decimal] = []
        amounts_to_compare.extend(self.collect_total_sum(total_amount_field))
        if advance_payments_field is not None:
            amounts_to_compare.extend(
                self.collect_advances_sum(advance_payments_field, errors),
            )
        self.all_equal(amounts_to_compare, errors)

        return self._result(errors)
