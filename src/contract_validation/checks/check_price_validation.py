from decimal import Decimal
from typing import cast

from app.domain.entities.single_supplier_fields import (
    Specification,
    SpecPositionsField,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .base import BaseCheck
from .deps import Requires
from .errors import InsufficientCheckDataError


class CheckPriceValidation(BaseCheck):
    spec_positions_field = Requires(SpecPositionsField)
    total_amount_field = Requires(TotalAmountField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance

    async def execute(self) -> CheckExecutionResult:
        spec_positions_field = cast("SpecPositionsField", self.spec_positions_field)
        total_amount_field = cast("TotalAmountField", self.total_amount_field)

        positions = Specification(spec_positions_field.value)
        total_payment = total_amount_field.value.total
        label = self.__class__.__name__

        if not positions.has_position_totals():
            raise InsufficientCheckDataError(
                label,
                "cannot calculate positions total for comparison",
            )

        errors = list(positions.validate_cost_calculation(tolerance=self.tolerance))
        errors.extend(
            positions.compare_total_with(total_payment, tolerance=self.tolerance)
        )
        return self._result(errors)
