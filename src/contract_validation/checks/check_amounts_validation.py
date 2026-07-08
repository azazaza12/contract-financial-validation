from decimal import Decimal
from typing import cast

from app.domain.entities.errors.checks import AmountDiscrepancyError, BaseCheckError
from app.domain.entities.single_supplier_fields import (
    AdvancePaymentsField,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .amount_basis import use_gross_basis
from .base import BaseCheck
from .deps import CheckServices, OptionalDep, Requires
from .errors import InsufficientCheckDataError


class CheckTotalAmountsValidation(BaseCheck):
    total_amount_field = Requires(TotalAmountField)
    advance_payments_field = OptionalDep(AdvancePaymentsField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance
        self.errors: list[BaseCheckError] = []
        self.amounts_to_compare: list[Decimal] = []

    def _check_amounts_consistent(self) -> None:
        if not self.amounts_to_compare:
            return
        reference_value = self.amounts_to_compare[0]
        for value in self.amounts_to_compare[1:]:
            difference = abs(value - reference_value)
            if difference > self.tolerance:
                self.errors.append(
                    AmountDiscrepancyError(
                        value=value,
                        reference_value=reference_value,
                        difference=difference,
                    ),
                )

    def _collect_total_amounts(
        self,
        total_amount_field: TotalAmountField,
        *,
        use_gross: bool,
    ) -> None:
        total_sum = total_amount_field.value.total.amount_in_basis(use_gross=use_gross)
        if total_sum is not None:
            self.amounts_to_compare.append(total_sum)

        taxes_sum = total_amount_field.value.tax_payments.amount_in_basis(
            use_gross=use_gross
        )
        if taxes_sum is not None:
            self.amounts_to_compare.append(taxes_sum)

    def _collect_advances_sum(
        self,
        advance_payments_field: AdvancePaymentsField,
        *,
        use_gross: bool,
    ) -> None:
        advances_sum: Decimal | None = None
        for advance_payment in advance_payments_field.value:
            total_amount = (
                advance_payment.total.amount_in_basis(use_gross=use_gross)
                if advance_payment.total is not None
                else None
            )
            payments_sum = advance_payment.payment_lines.amount_in_basis(
                use_gross=use_gross
            )

            if total_amount is not None and payments_sum is not None:
                diff = abs(total_amount - payments_sum)
                if diff > self.tolerance:
                    self.errors.append(
                        AmountDiscrepancyError(
                            reference_value=total_amount,
                            value=payments_sum,
                            difference=diff,
                        )
                    )

            amount = total_amount if total_amount is not None else payments_sum
            if amount is not None:
                advances_sum = (advances_sum or Decimal("0.00")) + amount

        if advances_sum is not None:
            self.amounts_to_compare.append(advances_sum)

    async def execute(self, check_services: CheckServices) -> CheckExecutionResult:  # noqa: ARG002
        self.errors = []
        self.amounts_to_compare = []

        total_amount_field = cast("TotalAmountField", self.total_amount_field)
        advance_payments_field = cast(
            "AdvancePaymentsField | None",
            self.advance_payments_field,
        )

        group = [total_amount_field.value.total, *total_amount_field.value.taxes]
        if advance_payments_field is not None:
            for advance_payment in advance_payments_field.value:
                if advance_payment.total is not None:
                    group.append(advance_payment.total)
                group.extend(advance_payment.payments)
        use_gross = use_gross_basis(group)

        self._collect_total_amounts(total_amount_field, use_gross=use_gross)
        if advance_payments_field is not None:
            self._collect_advances_sum(advance_payments_field, use_gross=use_gross)

        if not self.amounts_to_compare:
            raise InsufficientCheckDataError(
                self.__class__.__name__,
                "no amounts found to compare",
            )

        self._check_amounts_consistent()
        return self._result(self.errors)
