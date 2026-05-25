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

    @staticmethod
    def _has_any_position_line_total(positions: list[SpecPosition]) -> bool:
        return any(position.total_price is not None for position in positions)

    def _collect_position_errors(
        self,
        spec_positions: list[SpecPosition],
    ) -> tuple[Decimal, list[BaseCheckError]]:
        total_calculated = Decimal("0.00")
        errors: list[BaseCheckError] = []
        for count, spec_position in enumerate(spec_positions, start=1):
            quantity = spec_position.quantity
            price = spec_position.unit_price
            position_total_amount = spec_position.total_price

            if position_total_amount is None:
                continue

            if position_total_amount <= 0:
                errors.append(AmountNotPositiveError(value=position_total_amount))
            else:
                total_calculated += position_total_amount

            if quantity is None or price is None:
                continue

            if price <= 0:
                errors.append(AmountNotPositiveError(value=price))
                continue

            position_calculated = quantity * price
            diff = abs(position_total_amount - position_calculated)
            if diff > self.tolerance:
                errors.append(
                    PositionCostDiscrepancyError(
                        count=count,
                        position_name=spec_position.name,
                        cost=position_total_amount,
                        calculated_cost=position_calculated,
                        difference_sum=diff,
                    ),
                )
        return total_calculated, errors

    async def execute(self, _check_services: CheckServices) -> CheckExecutionResult:
        self.spec_positions_field = cast(
            "SpecPositionsField",
            self.spec_positions_field,
        )
        self.total_amount_field = cast(
            "TotalAmountField",
            self.total_amount_field,
        )
        spec_positions = self.spec_positions_field.value
        total_payment = self.total_amount_field.value.total
        total_amount = (
            total_payment.amount.value if total_payment.amount is not None else None
        )
        label = self.__class__.__name__

        if total_amount is None:
            raise InsufficientCheckDataError(
                label,
                "no contract total amount for comparison",
            )

        total_calculated, errors = self._collect_position_errors(spec_positions)

        has_position_totals = self._has_any_position_line_total(spec_positions)

        if total_amount <= 0:
            errors.append(AmountNotPositiveError(value=total_amount))
        else:
            if total_calculated == 0 and not has_position_totals:
                raise InsufficientCheckDataError(
                    label,
                    "cannot calculate positions total for comparison",
                )
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
