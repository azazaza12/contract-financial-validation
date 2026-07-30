from decimal import Decimal
from typing import cast

from app.domain.entities.single_supplier_fields import (
    AdvancePaymentList,
    AdvancePaymentsField,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .base import BaseCheck
from .deps import OptionalDep, Requires
from .errors import InsufficientCheckDataError


class CheckVatCalculation(BaseCheck):
    total_amount_field = Requires(TotalAmountField)
    advance_payments_field = OptionalDep(AdvancePaymentsField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance

    async def execute(self) -> CheckExecutionResult:
        total_amount_field = cast("TotalAmountField", self.total_amount_field)
        advance_payments_field = cast(
            "AdvancePaymentsField | None",
            self.advance_payments_field,
        )

        advances = (
            advance_payments_field.value
            if advance_payments_field is not None
            else AdvancePaymentList([])
        )

        if (
            not total_amount_field.value.has_vat_calculation_data()
            and not advances.has_vat_calculation_data()
        ):
            raise InsufficientCheckDataError(
                self.__class__.__name__,
                "no payments with amount, VAT amount and VAT rate to verify",
            )

        errors = [
            *total_amount_field.value.validate_vat_calculation(
                tolerance=self.tolerance
            ),
            *advances.validate_vat_calculation(tolerance=self.tolerance),
        ]
        return self._result(errors)
