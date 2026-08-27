from typing import cast

from app.domain.entities.errors.checks import AmountNotFoundError, BaseCheckError
from app.domain.entities.single_supplier_fields import (
    AdvancePaymentsField,
    SpecPositionsField,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .base import BaseCheck
from .deps import OptionalDep


class CheckValuesValidation(BaseCheck):
    total_amount_field = OptionalDep(TotalAmountField)
    advance_payments_field = OptionalDep(AdvancePaymentsField)
    spec_positions_field = OptionalDep(SpecPositionsField)

    async def execute(self) -> CheckExecutionResult:
        errors: list[BaseCheckError] = []

        total_amount_field = cast("TotalAmountField | None", self.total_amount_field)
        advance_payments_field = cast(
            "AdvancePaymentsField | None", self.advance_payments_field
        )
        spec_positions_field = cast(
            "SpecPositionsField | None", self.spec_positions_field
        )

        if total_amount_field is not None:
            errors.extend(total_amount_field.validate_positivity())
            errors.extend(total_amount_field.validate_presence())
        else:
            errors.append(AmountNotFoundError())
        if advance_payments_field is not None:
            errors.extend(advance_payments_field.validate_positivity())
        if spec_positions_field is not None:
            errors.extend(spec_positions_field.validate_positivity())

        return self._result(errors)
