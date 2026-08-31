from decimal import Decimal
from typing import cast

from app.domain.entities.errors import BaseCheckError
from app.domain.entities.single_supplier_fields import (
    TotalAmountField,
    TotalAmountUpperBoundField,
)
from app.domain.entities.validation import CheckExecutionResult

from .base import BaseCheck
from .deps import Requires


class CheckTotalAmountUpperBound(BaseCheck):
    total_amount_field = Requires(TotalAmountField)
    upper_bound_amount_field = Requires(TotalAmountUpperBoundField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance

    async def execute(self) -> CheckExecutionResult:
        errors: list[BaseCheckError] = []
        total_amount_field = cast("TotalAmountField", self.total_amount_field)
        upper_bound_amount_field = cast(
            "TotalAmountUpperBoundField", self.upper_bound_amount_field
        )
        errors.extend(
            upper_bound_amount_field.compare(
                total_amount_field.value.total, self.tolerance
            )
        )
        return self._result(errors)
