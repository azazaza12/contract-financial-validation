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
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .base import BaseCheck
from .deps import CheckServices, Requires
from .errors import InsufficientCheckDataError


class CheckPaymentPercentValidation(BaseCheck):
    advance_payments_field = Requires(AdvancePaymentsField)
    total_amount_field = Requires(TotalAmountField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance

    async def execute(self, check_services: CheckServices) -> CheckExecutionResult:  # noqa: ARG002
        advance_payments_field = cast(
            "AdvancePaymentsField",
            self.advance_payments_field,
        )
        total_amount_field = cast("TotalAmountField", self.total_amount_field)
        errors: list[BaseCheckError] = []
        advance_payments = advance_payments_field.value
        total_amount = total_amount_field.value.total.amount_value

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

        total_percent = Decimal("0.00")
        for advance_payment in advance_payments:
            if advance_payment.percent is not None:
                total_percent += advance_payment.percent

        if total_amount is not None:
            for advance_payment in advance_payments:
                errors.extend(
                    self._validate_advance_amount(advance_payment, total_amount)
                )

        if abs(total_percent - Decimal("100.00")) > self.tolerance:
            errors.append(
                PaymentPercentSumDiscrepancyError(total_percent=total_percent)
            )
        return self._result(errors)

    def _validate_advance_amount(
        self,
        advance_payment: AdvancePayment,
        total_amount: Decimal,
    ) -> list[BaseCheckError]:
        if advance_payment.percent is None:
            return []
        resolved = advance_payment.resolved_total
        line_amount = resolved.amount_value if resolved is not None else None
        if line_amount is None:
            return []
        expected_amount = total_amount * advance_payment.percent / Decimal("100.00")
        if abs(line_amount - expected_amount) > self.tolerance:
            return [
                PaymentAmountPercentDiscrepancyError(
                    amount=line_amount,
                    expected_amount=expected_amount,
                    percent=advance_payment.percent,
                    contract_total_amount=total_amount,
                )
            ]
        return []
