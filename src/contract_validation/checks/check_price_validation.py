from decimal import Decimal
from typing import cast

from app.domain.checks.base import BaseCheck
from app.domain.entities.errors import (
    AmountDiscrepancyError,
    AmountNotFoundError,
    AmountNotPositiveError,
    BaseCheckError,
    PositionCostDiscrepancyError,
)
from app.domain.entities.single_supplier_fields import (
    SpecPositionsField,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .deps import Requires


class CheckPriceValidation(BaseCheck):
    spec_positions_field = Requires(SpecPositionsField)
    total_amount_field = Requires(TotalAmountField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance

    async def execute(self) -> CheckExecutionResult:
        self.spec_positions_field = cast(
            "SpecPositionsField",
            self.spec_positions_field,
        )
        self.total_amount_field = cast(
            "TotalAmountField",
            self.total_amount_field,
        )
        errors: list[BaseCheckError] = []

        spec_positions = self.spec_positions_field.value
        total_payment = self.total_amount_field.value.total
        total_amount = (
            total_payment.amount.value if total_payment.amount is not None else None
        )
        total_calculated = Decimal("0.0")

        for count, spec_position in enumerate(spec_positions, start=1):
            quantity_dec = Decimal(str(spec_position.quantity))
            price = spec_position.unit_price
            if price <= 0:
                errors.append(AmountNotPositiveError(value=price))
            position_total_amount_calculated = quantity_dec * price
            total_calculated += position_total_amount_calculated
            position_total_amount = spec_position.total_price
            if position_total_amount <= 0:
                errors.append(AmountNotPositiveError(value=position_total_amount))
            position_name = spec_position.name
            position_amount_difference = abs(
                position_total_amount - position_total_amount_calculated,
            )

            if position_amount_difference > self.tolerance:
                errors.append(
                    PositionCostDiscrepancyError(
                        count=count,
                        position_name=position_name,
                        cost=position_total_amount,
                        calculated_cost=position_total_amount_calculated,
                        difference_sum=position_amount_difference,
                    ),
                )

        if total_amount is None:
            errors.append(AmountNotFoundError())
        elif total_amount <= 0:
            errors.append(AmountNotPositiveError(value=total_amount))
        else:
            difference = abs(total_calculated - total_amount)
            if difference > self.tolerance:
                errors.append(
                    AmountDiscrepancyError(
                        reference_value=total_amount,
                        value=total_calculated,
                        difference=difference,
                    ),
                )

        return self._result(errors)
