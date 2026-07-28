from decimal import Decimal
from typing import cast

from app.domain.entities.errors.checks import AmountDiscrepancyError, BaseCheckError
from app.domain.entities.single_supplier_fields import (
    AdvancePayment,
    AdvancePaymentsField,
    Payment,
    PaymentList,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .base import BaseCheck
from .deps import OptionalDep, Requires
from .errors import InsufficientCheckDataError


class CheckTotalAmountsValidation(BaseCheck):
    total_amount_field = Requires(TotalAmountField)
    advance_payments_field = OptionalDep(AdvancePaymentsField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance
        self.errors: list[BaseCheckError] = []


    def _check_advance_payment(self, advance_payment: AdvancePayment) -> None:
        if advance_payment.total is None:
            return
        payments_sum = advance_payment.payments.summed
        if payments_sum is None:
            return
        self.errors.extend(payments_sum.compare(advance_payment.total, tolerance=self.tolerance))



    async def execute(self) -> CheckExecutionResult:
        self.errors = []

        total_amount_field = cast("TotalAmountField", self.total_amount_field)
        advance_payments_field = cast(
            "AdvancePaymentsField | None", self.advance_payments_field
        )

        total = total_amount_field.value.total
        if total.amount_value is None:
            raise InsufficientCheckDataError(
                self.__class__.__name__,
                "no amounts found to compare",
            )
        taxes = total_amount_field.value.taxes.summed
        if taxes is not None:
            self.errors.extend(taxes.compare(total, tolerance=self.tolerance))

        if advance_payments_field is not None:
            advance_payments: list[Payment] = []
            for advance_payment in advance_payments_field.value:
                self._check_advance_payment(advance_payment)

                resolved = advance_payment.resolved
                if resolved is not None:
                    advance_payments.append(resolved)
            advances_sum = PaymentList(advance_payments).summed
            if advances_sum is not None:
                self.errors.extend(
                    advances_sum.compare(total, tolerance=self.tolerance)
                )

        return self._result(self.errors)
