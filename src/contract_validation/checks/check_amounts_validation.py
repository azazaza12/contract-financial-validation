import logging
from decimal import Decimal

from app.domain.entities.validation import CheckExecutionResult
from app.domain.entities.validation_errors import (
    BaseResultChecker,
    AmountDiscrepancyCheckResult,
)
from app.domain.checks.base import BaseCheck
from app.domain.entities.single_supplier import (
    TotalAmountField,
    AdvancePaymentsField,
    Payment,
)

logger = logging.getLogger(__name__)


class CheckTotalAmountsValidation(BaseCheck):
    def __init__(self, tolerance: Decimal | None = None):
        if tolerance is None:
            from app.config import ValidationSettings

            tolerance = ValidationSettings().AMOUNT_TOLERANCE
        self.tolerance = tolerance

    def all_equal(self, values: list[Decimal], errors: list[BaseResultChecker]) -> None:
        if not values:
            return
        reference_value = values[0]
        for value in values[1:]:
            difference = abs(value - reference_value)
            if difference > self.tolerance:
                errors.append(
                    AmountDiscrepancyCheckResult(
                        value=value,
                        reference_value=reference_value,
                        difference=difference,
                    )
                )

    def collect_sums_from_payments(self, payments: list[Payment]) -> Decimal | None:
        total_amount_sum = Decimal("0.00")
        has_any = False
        for payment in payments:
            if payment.amount is not None:
                total_amount_sum += payment.amount.value
                has_any = True
        if has_any:
            return total_amount_sum
        return

    def collect_total_sum(self, total_amount_field: TotalAmountField) -> list[Decimal]:
        target: list[Decimal] = []
        total_amount_sum = self.collect_sums_from_payments(
            [total_amount_field.value.total]
        )
        if total_amount_sum is not None:
            target.append(total_amount_sum)
        if total_amount_field.value.taxes is not None:
            taxes_total_amount_sum = self.collect_sums_from_payments(
                total_amount_field.value.taxes
            )
            if taxes_total_amount_sum is not None:
                target.append(taxes_total_amount_sum)
        return target

    def collect_advances_sum(
        self,
        advance_payments_field: AdvancePaymentsField,
        errors: list[BaseResultChecker],
    ) -> list[Decimal]:
        target: list[Decimal] = []
        total_amount_sum = Decimal("0.00")
        total_payments_sum = Decimal("0.00")
        has_any = False
        for adv in advance_payments_field.value:
            total_amount = None
            adv_amount_sum = None
            if adv.total is not None:
                total_amount = self.collect_sums_from_payments([adv.total])
                if total_amount is not None:
                    total_amount_sum += total_amount
                    has_any = True
            if adv.payments is not None:
                adv_amount_sum = self.collect_sums_from_payments(adv.payments)
                if adv_amount_sum is not None:
                    total_payments_sum += adv_amount_sum
                    has_any = True
            if total_amount is not None and adv_amount_sum is not None:
                diff = abs(total_amount - adv_amount_sum)
                if diff > self.tolerance:
                    errors.append(
                        AmountDiscrepancyCheckResult(
                            reference_value=total_amount,
                            value=adv_amount_sum,
                            difference=diff,
                        )
                    )
        if has_any:
            target.append(total_amount_sum)
            target.append(total_payments_sum)
        return target

    async def execute(
        self,
        total_amount_field: TotalAmountField,
        advance_payments_field: AdvancePaymentsField | None,
    ) -> CheckExecutionResult:

        errors: list[BaseResultChecker] = []
        amounts_to_compare: list[Decimal] = []
        amounts_to_compare.extend(self.collect_total_sum(total_amount_field))
        if advance_payments_field is not None:
            amounts_to_compare.extend(
                self.collect_advances_sum(advance_payments_field, errors)
            )
        self.all_equal(amounts_to_compare, errors)

        return self._result(errors)
