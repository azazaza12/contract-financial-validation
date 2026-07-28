from decimal import Decimal
from typing import cast

from app.domain.entities.errors.checks import BaseCheckError
from app.domain.entities.single_supplier_fields import (
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

    async def execute(self) -> CheckExecutionResult:
        self.errors = []

        total_amount_field = cast("TotalAmountField", self.total_amount_field)
        advance_payments_field = cast(
            "AdvancePaymentsField | None", self.advance_payments_field
        )

        if not total_amount_field.has_amounts() and (
            advance_payments_field is None or not advance_payments_field.has_amounts()
        ):
            raise InsufficientCheckDataError(
                self.__class__.__name__,
                "no amount or VAT amount found",
            )

        total = total_amount_field.value.total
        taxes = total_amount_field.value.taxes.summed
        if taxes is not None:
            self.errors.extend(taxes.compare(total, tolerance=self.tolerance))

        if advance_payments_field is not None:
            advance_payments: list[Payment] = []
            for advance_payment in advance_payments_field.value:
                self.errors.extend(
                    advance_payment.compare_payments_with_total(
                        tolerance=self.tolerance
                    )
                )

                resolved = advance_payment.resolved
                if resolved is not None:
                    advance_payments.append(resolved)
            advances_sum = PaymentList(advance_payments).summed
            if advances_sum is not None:
                self.errors.extend(
                    advances_sum.compare(total, tolerance=self.tolerance)
                )

        return self._result(self.errors)
