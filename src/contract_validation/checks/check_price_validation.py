import logging
from decimal import Decimal

from app.domain.checks.base import BaseCheck
from app.domain.entities.single_supplier import SpecPositionsField, TotalAmountField
from app.domain.entities.validation import BaseResultChecker, CheckExecutionResult
from app.domain.entities.validation_errors import (
    AmountDiscrepancyCheckResult,
    AmountNotFoundCheckResult,
    AmountNotPositiveCheckResult,
    PositionCostDiscrepancyCheckResult,
)


logger = logging.getLogger(__name__)


class CheckPriceValidation(BaseCheck):
    def __init__(self, tolerance: Decimal):
        self.tolerance = tolerance

    async def execute(
        self,
        spec_positions_field: SpecPositionsField,
        total_amount_field: TotalAmountField,
    ) -> CheckExecutionResult:
        errors: list[BaseResultChecker] = []

        spec_positions = spec_positions_field.value
        total_payment = total_amount_field.value.total
        total_amount = (
            total_payment.amount.value if total_payment.amount is not None else None
        )
        total_calculated = Decimal(0.0)

        for count, spec_position in enumerate(spec_positions, start=1):
            quantity_dec = Decimal(str(spec_position.quantity))
            price = spec_position.unit_price
            if price <= 0:
                errors.append(AmountNotPositiveCheckResult(value=price))
            position_total_amount_calculated = quantity_dec * price
            total_calculated += position_total_amount_calculated
            position_total_amount = spec_position.total_price
            if position_total_amount <= 0:
                errors.append(AmountNotPositiveCheckResult(value=position_total_amount))
            position_name = spec_position.name
            position_amount_difference = abs(
                position_total_amount - position_total_amount_calculated
            )

            if position_amount_difference > self.tolerance:
                errors.append(
                    PositionCostDiscrepancyCheckResult(
                        count=count,
                        position_name=position_name,
                        cost=position_total_amount,
                        calculated_cost=position_total_amount_calculated,
                        difference_sum=position_amount_difference,
                    )
                )

        if total_amount is None:
            errors.append(AmountNotFoundCheckResult())
        elif total_amount <= 0:
            errors.append(AmountNotPositiveCheckResult(value=total_amount))
        else:
            difference = abs(total_calculated - total_amount)
            if difference > self.tolerance:
                errors.append(
                    AmountDiscrepancyCheckResult(
                        reference_value=total_amount,
                        value=total_calculated,
                        difference=difference,
                    )
                )

        if errors:
            logger.info(
                "[%s] found errors: [%d]", self.__class__.__name__, len(errors)
            )
        else:
            logger.info("[%s] succeeded", self.__class__.__name__)
        return self._result(errors)
