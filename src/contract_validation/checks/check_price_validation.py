from decimal import Decimal
from typing import cast

from app.domain.checks.base import BaseCheck
from app.domain.entities.errors import (
    AmountDiscrepancyError,
    AmountNotPositiveError,
    BaseCheckError,
    PositionCostDiscrepancyError,
)
from app.domain.entities.single_supplier_fields import (
    SpecPosition,
    SpecPositionsField,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .deps import CheckServices, Requires
from .errors import InsufficientCheckDataError


class CheckPriceValidation(BaseCheck):
    spec_positions_field = Requires(SpecPositionsField)
    total_amount_field = Requires(TotalAmountField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance
        self.errors: list[BaseCheckError] = []

    @staticmethod
    def _has_any_position_line_total(positions: list[SpecPosition]) -> bool:
        return any(position.total_price is not None for position in positions)

    def _validate_position_lines_and_sum(
        self, spec_positions: list[SpecPosition]
    ) -> Decimal:
        total_calculated = Decimal("0.00")
        for count, spec_position in enumerate(spec_positions, start=1):
            quantity = spec_position.quantity
            price = spec_position.unit_price
            position_total_amount = spec_position.total_price

            if position_total_amount is None:
                continue

            if position_total_amount <= 0:
                self.errors.append(AmountNotPositiveError(value=position_total_amount))
            else:
                total_calculated += position_total_amount

            if quantity is None or price is None:
                continue

            if price <= 0:
                self.errors.append(AmountNotPositiveError(value=price))
                continue

            position_calculated = quantity * price
            diff = abs(position_total_amount - position_calculated)
            if diff > self.tolerance:
                self.errors.append(
                    PositionCostDiscrepancyError(
                        count=count,
                        position_name=spec_position.name,
                        cost=position_total_amount,
                        calculated_cost=position_calculated,
                        difference_sum=diff,
                    ),
                )
        return total_calculated

    async def execute(self, _check_services: CheckServices) -> CheckExecutionResult:
        self.errors = []

        spec_positions_field = cast(SpecPositionsField, self.spec_positions_field)
        total_amount_field = cast("TotalAmountField", self.total_amount_field)

        spec_positions = spec_positions_field.value
        total_payment = total_amount_field.value.total
        total_amount = (
            total_payment.amount.value if total_payment.amount is not None else None
        )
        label = self.__class__.__name__

        if total_amount is None:
            raise InsufficientCheckDataError(
                label,
                "no contract total amount for comparison",
            )

        positions_total = self._validate_position_lines_and_sum(spec_positions)

        has_position_totals = self._has_any_position_line_total(spec_positions)

        if total_amount <= 0:
            self.errors.append(AmountNotPositiveError(value=total_amount))
        elif positions_total == 0 and not has_position_totals:
            raise InsufficientCheckDataError(
                label,
                "cannot calculate positions total for comparison",
            )
        else:
            difference = abs(positions_total - total_amount)
            if difference > self.tolerance:
                self.errors.append(
                    AmountDiscrepancyError(
                        reference_value=total_amount,
                        value=positions_total,
                        difference=difference,
                    ),
                )

        return self._result(self.errors)
