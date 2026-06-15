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


def _calculate_advance_line_amount(adv: AdvancePayment) -> Decimal | None:
    if (
        adv.total is not None
        and adv.total.amount is not None
        and adv.total.amount.value is not None
    ):
        return adv.total.amount.value
    s: Decimal | None = None
    for p in adv.payments:
        if p.amount is None or p.amount.value is None:
            continue
        s = (s or Decimal("0.00")) + p.amount.value
    return s


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
        payments = advance_payments_field.value
        total_payment = total_amount_field.value.total
        total_amount = (
            total_payment.amount.value if total_payment.amount is not None else None
        )

        label = self.__class__.__name__

        if not payments:
            raise InsufficientCheckDataError(
                label,
                "no advance payment records to validate",
            )

        if not any(advance_payment.percent is not None for advance_payment in payments):
            raise InsufficientCheckDataError(
                label,
                "no advance payment percents to validate",
            )

        total_percent = Decimal("0.00")

        for advance_payment in payments:
            if advance_payment.percent is None:
                continue

            total_percent += advance_payment.percent
            line_amount = _calculate_advance_line_amount(advance_payment)
            if total_amount is None or line_amount is None:
                continue

            expected_amount = total_amount * advance_payment.percent / Decimal("100.00")
            diff_amount = abs(line_amount - expected_amount)
            if diff_amount <= self.tolerance:
                continue

            errors.append(
                PaymentAmountPercentDiscrepancyError(
                    amount=line_amount,
                    expected_amount=expected_amount,
                    percent=advance_payment.percent,
                    contract_total_amount=total_amount,
                ),
            )

        if abs(total_percent - Decimal("100.00")) > self.tolerance:
            errors.append(
                PaymentPercentSumDiscrepancyError(total_percent=total_percent)
            )
        return self._result(errors)
