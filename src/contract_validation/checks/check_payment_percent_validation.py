from decimal import Decimal
from typing import cast

from app.domain.entities.errors.checks import (
    BaseCheckError,
    PaymentAmountPercentDiscrepancyError,
    PaymentPercentSumDiscrepancyError,
)
from app.domain.entities.single_supplier_fields import (
    AdvancePayment,
    AdvancePaymentsField,
    Basis,
    Payment,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .amount_basis import select_basis
from .base import BaseCheck
from .deps import CheckServices, Requires
from .errors import InsufficientCheckDataError


class CheckPaymentPercentValidation(BaseCheck):
    advance_payments_field = Requires(AdvancePaymentsField)
    total_amount_field = Requires(TotalAmountField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance

    def _select_basis(
        self, total_payment: Payment, advance_payments: list[AdvancePayment]
    ) -> Basis:
        group = [total_payment]
        for advance_payment in advance_payments:
            if (
                advance_payment.total is not None
                and advance_payment.total.amount_value is not None
            ):
                group.append(advance_payment.total)
            else:
                group.extend(advance_payment.payments)
        return select_basis(group)

    def _validate_advance_amount(
        self,
        advance_payment: AdvancePayment,
        total_payment: Payment,
        *,
        basis: Basis,
    ) -> BaseCheckError | None:
        if advance_payment.percent is None:
            return None
        total_amount = total_payment.amount_in_basis(basis)
        line_amount = advance_payment.amount_in_basis(basis)
        if total_amount is None or line_amount is None:
            return None
        expected_amount = total_amount * advance_payment.percent / Decimal("100.00")
        if abs(line_amount - expected_amount) <= self.tolerance:
            return None
        return PaymentAmountPercentDiscrepancyError(
            amount=line_amount,
            expected_amount=expected_amount,
            percent=advance_payment.percent,
            contract_total_amount=total_amount,
        )

    async def execute(self, check_services: CheckServices) -> CheckExecutionResult:  # noqa: ARG002
        advance_payments_field = cast(
            "AdvancePaymentsField",
            self.advance_payments_field,
        )
        total_amount_field = cast("TotalAmountField", self.total_amount_field)
        advance_payments = advance_payments_field.value
        total_payment = total_amount_field.value.total
        label = self.__class__.__name__

        if not advance_payments:
            raise InsufficientCheckDataError(
                label,
                "no advance payment records to validate",
            )

        if not any(
            advance_payment.percent is not None for advance_payment in advance_payments
        ):
            raise InsufficientCheckDataError(
                label,
                "no advance payment percents to validate",
            )

        basis = self._select_basis(total_payment, advance_payments)

        errors: list[BaseCheckError] = []
        for advance_payment in advance_payments:
            error = self._validate_advance_amount(
                advance_payment, total_payment, basis=basis
            )
            if error is not None:
                errors.append(error)

        total_percent = Decimal("0.00")
        for advance_payment in advance_payments:
            if advance_payment.percent is not None:
                total_percent += advance_payment.percent

        if abs(total_percent - Decimal("100.00")) > self.tolerance:
            errors.append(
                PaymentPercentSumDiscrepancyError(total_percent=total_percent)
            )
        return self._result(errors)
