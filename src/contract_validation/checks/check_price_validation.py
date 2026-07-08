from decimal import Decimal
from typing import cast

from app.domain.entities.errors.checks import (
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

from .base import BaseCheck
from .deps import CheckServices, Requires
from .errors import InsufficientCheckDataError


class CheckPriceValidation(BaseCheck):
    spec_positions_field = Requires(SpecPositionsField)
    total_amount_field = Requires(TotalAmountField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance
        self.errors: list[BaseCheckError] = []

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

    async def execute(self, check_services: CheckServices) -> CheckExecutionResult:  # noqa: ARG002
        self.errors = []

        spec_positions_field = cast("SpecPositionsField", self.spec_positions_field)
        total_amount_field = cast("TotalAmountField", self.total_amount_field)

        spec_positions = spec_positions_field.value
        total_payment = total_amount_field.value.total
        label = self.__class__.__name__

        candidate_totals = [
            candidate
            for candidate in (
                total_payment.amount_including_vat,
                total_payment.amount_excluding_vat,
            )
            if candidate is not None
        ]
        if not candidate_totals:
            raw_total = total_payment.amount_value
            if raw_total is not None:
                candidate_totals = [raw_total]

        if not candidate_totals:
            raise InsufficientCheckDataError(
                label,
                "no contract total amount for comparison",
            )

        positions_total = self._validate_position_lines_and_sum(spec_positions)

        has_position_totals = any(
            position.total_price is not None for position in spec_positions
        )

        representative_total = candidate_totals[0]
        if representative_total <= 0:
            self.errors.append(AmountNotPositiveError(value=representative_total))
        elif positions_total == 0 and not has_position_totals:
            raise InsufficientCheckDataError(
                label,
                "cannot calculate positions total for comparison",
            )
        else:
            closest_total = min(
                candidate_totals,
                key=lambda candidate: abs(positions_total - candidate),
            )
            difference = abs(positions_total - closest_total)
            if difference > self.tolerance:
                self.errors.append(
                    AmountDiscrepancyError(
                        reference_value=closest_total,
                        value=positions_total,
                        difference=difference,
                    ),
                )

        return self._result(self.errors)
