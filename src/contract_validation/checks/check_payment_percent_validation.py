from decimal import Decimal
from typing import cast

from app.domain.entities.errors.checks import (
    BaseCheckError,
    PaymentPercentSumDiscrepancyError,
)
from app.domain.entities.single_supplier_fields import (
    AdvancePaymentsField,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .base import BaseCheck
from .deps import Requires
from .errors import InsufficientCheckDataError


class CheckPaymentPercentValidation(BaseCheck):
    advance_payments_field = Requires(AdvancePaymentsField)
    total_amount_field = Requires(TotalAmountField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance

    async def execute(self) -> CheckExecutionResult:
        advance_payments_field = cast(
            "AdvancePaymentsField", self.advance_payments_field
        )
        total_amount_field = cast("TotalAmountField", self.total_amount_field)
        advance_payments = advance_payments_field.value
        total_payment = total_amount_field.value.total
        label = self.__class__.__name__

        if not advance_payments:
            raise InsufficientCheckDataError(
                label,
                "no advance payment records to validate",
            )

        advances_sum = advance_payments.summed
        if advances_sum is None or advances_sum.percent is None:
            raise InsufficientCheckDataError(
                label,
                "no advance payment percents to validate",
            )

        errors: list[BaseCheckError] = []
        for advance_payment in advance_payments:
            errors.extend(
                advance_payment.compare_amount_with_percent(
                    total_payment, tolerance=self.tolerance
                )
            )

        total_percent = advances_sum.percent
        if abs(total_percent - Decimal("100.00")) > self.tolerance:
            errors.append(
                PaymentPercentSumDiscrepancyError(total_percent=total_percent)
            )
        return self._result(errors)
