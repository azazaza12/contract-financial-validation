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


class CheckTaxRatesValidation(BaseCheck):
    total_amount_field = Requires(TotalAmountField)
    advance_payments_field = OptionalDep(AdvancePaymentsField)

    async def execute(self) -> CheckExecutionResult:
        total_amount_field = cast("TotalAmountField", self.total_amount_field)
        advance_payments_field = cast(
            "AdvancePaymentsField | None", self.advance_payments_field
        )

        ta = total_amount_field.value
        contract_rate = ta.total.vat.rate
        tax_rates = ta.taxes.vat_rates
        advances_have_rate = (
            advance_payments_field is not None
            and advance_payments_field.value.has_vat_rate()
        )

        if not (contract_rate is not None or tax_rates or advances_have_rate):
            raise InsufficientCheckDataError(
                self.__class__.__name__,
                "no VAT rates found in contract, taxes, or advances",
            )

        errors: list[BaseCheckError] = []
        if contract_rate is not None:
            errors.extend(ta.taxes.validate_vat_rate([contract_rate]))

        if advance_payments_field is not None and advance_payments_field.value:
            reference = (
                sorted(tax_rates)
                if tax_rates
                else ([contract_rate] if contract_rate is not None else [])
            )
            errors.extend(advance_payments_field.value.validate_vat_rate(reference))

        return self._result(errors)
