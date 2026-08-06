from decimal import Decimal
from typing import cast

from app.domain.entities.errors.checks import BaseCheckError
from app.domain.entities.single_supplier_fields import (
    AdvancePaymentsField,
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

        total = total_amount_field.value.total
        if not total.numeric_moneys():
            raise InsufficientCheckDataError(
                self.__class__.__name__,
                "no amount or VAT amount found",
            )

        self.errors.extend(
            total_amount_field.value.taxes.compare(total, tolerance=self.tolerance)
        )

        if advance_payments_field is not None:
            self.errors.extend(
                advance_payments_field.value.compare(total, tolerance=self.tolerance)
            )

        return self._result(self.errors)
