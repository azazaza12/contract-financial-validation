from decimal import Decimal
from typing import cast

from app.domain.checks.base import BaseCheck
from app.domain.entities.errors import (
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

from .deps import Requires


def _calculate_advance_line_amount(adv: AdvancePayment) -> Decimal | None:
    if adv.total is not None and adv.total.amount is not None:
        return adv.total.amount.value
    if not adv.payments:
        return None

    s = Decimal("0.00")
    has_any = False
    for p in adv.payments:
        if p.amount is None:
            continue
        s += p.amount.value
        has_any = True
    if not has_any:
        return None
    return s


class CheckPaymentPercentValidation(BaseCheck):
    advance_payments_field = Requires(AdvancePaymentsField)
    total_amount_field = Requires(TotalAmountField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance

    async def execute(
        self,
    ) -> CheckExecutionResult:
        self.advance_payments_field = cast(
            "AdvancePaymentsField",
            self.advance_payments_field,
        )
        self.total_amount_field = cast("TotalAmountField", self.total_amount_field)
        errors: list[BaseCheckError] = []
        payments = self.advance_payments_field.value
        total_payment = self.total_amount_field.value.total
        total_amount = (
            total_payment.amount.value if total_payment.amount is not None else None
        )

        if not payments:
            return self._result(errors)

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

        all_percents_specified = all(p.percent is not None for p in payments)
        if all_percents_specified:
            percent_diff = abs(total_percent - Decimal("100.00"))
            if percent_diff > self.tolerance:
                errors.append(
                    PaymentPercentSumDiscrepancyError(total_percent=total_percent)
                )
        if errors:
            return self._result(errors)

        return self._result(errors)
