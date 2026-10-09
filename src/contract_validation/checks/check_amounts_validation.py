from decimal import Decimal
from typing import cast

from contract_validation.entities.amount_comparison import (
    AmountDiscrepancy,
    ComparisonStatus,
    NormalizedAmountDiscrepancy,
    PaymentComparison,
)
from contract_validation.entities.contract_fields import (
    AdvancePaymentsField,
    TotalAmountField,
)
from contract_validation.entities.errors.checks import (
    AdvanceAmountDiscrepancyError,
    AdvanceVatAmountDiscrepancyError,
    BaseAmountDiscrepancyError,
    BaseCheckError,
    BaseNormalizedAmountDiscrepancyError,
    TaxesAmountDiscrepancyError,
    TaxesVatAmountDiscrepancyError,
)
from contract_validation.entities.validation import CheckExecutionResult

from .base import BaseCheck
from .deps import OptionalDep, Requires
from .errors import InsufficientCheckDataError


def _comparison_errors(
    comparison: PaymentComparison,
    *,
    amount_error_type: type[BaseNormalizedAmountDiscrepancyError],
    vat_amount_error_type: type[BaseAmountDiscrepancyError],
) -> list[BaseCheckError]:
    errors: list[BaseCheckError] = []
    if comparison.amount.status is ComparisonStatus.NOT_OK:
        amount_discrepancy = cast(
            "NormalizedAmountDiscrepancy", comparison.amount.discrepancy
        )
        errors.append(
            amount_error_type(
                value=amount_discrepancy.value,
                reference_value=amount_discrepancy.reference_value,
                difference=amount_discrepancy.difference,
                target_inclusion=amount_discrepancy.target_inclusion,
                operands=amount_discrepancy.operands,
                reference_operand=amount_discrepancy.reference_operand,
            )
        )
    if comparison.vat_amount.status is ComparisonStatus.NOT_OK:
        vat_amount_discrepancy = cast(
            "AmountDiscrepancy", comparison.vat_amount.discrepancy
        )
        errors.append(
            vat_amount_error_type(
                value=vat_amount_discrepancy.value,
                reference_value=vat_amount_discrepancy.reference_value,
                difference=vat_amount_discrepancy.difference,
            )
        )
    return errors


def _taxes_errors(comparison: PaymentComparison) -> list[BaseCheckError]:
    return _comparison_errors(
        comparison,
        amount_error_type=TaxesAmountDiscrepancyError,
        vat_amount_error_type=TaxesVatAmountDiscrepancyError,
    )


def _advance_errors(comparison: PaymentComparison) -> list[BaseCheckError]:
    return _comparison_errors(
        comparison,
        amount_error_type=AdvanceAmountDiscrepancyError,
        vat_amount_error_type=AdvanceVatAmountDiscrepancyError,
    )


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

        taxes_comparison = total_amount_field.value.taxes.compare_sum(
            total, tolerance=self.tolerance
        )
        self.errors.extend(_taxes_errors(taxes_comparison))

        if advance_payments_field is not None:
            advance_comparison = advance_payments_field.value.compare_sum(
                total, tolerance=self.tolerance
            )
            self.errors.extend(_advance_errors(advance_comparison))

        return self._result(self.errors)
