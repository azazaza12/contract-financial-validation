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

from .amount_basis import use_gross_basis
from .base import BaseCheck
from .deps import CheckServices, Requires
from .errors import InsufficientCheckDataError


def _calculate_advance_line_amount(
    adv: AdvancePayment,
    *,
    use_gross: bool,
) -> Decimal | None:
    if adv.total is not None:
        total = adv.total.amount_in_basis(use_gross=use_gross)
        if total is not None:
            return total
    s: Decimal | None = None
    for p in adv.payments:
        amount = p.amount_in_basis(use_gross=use_gross)
        if amount is None:
            continue
        s = (s or Decimal("0.00")) + amount
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

        group = [total_payment]
        for advance_payment in advance_payments:
            if (
                advance_payment.total is not None
                and advance_payment.total.amount_value is not None
            ):
                group.append(advance_payment.total)
            else:
                group.extend(advance_payment.payments)
        use_gross = use_gross_basis(group)

        total_amount = total_payment.amount_in_basis(use_gross=use_gross)

        total_percent = Decimal("0.00")
        for advance_payment in advance_payments:
            if advance_payment.percent is not None:
                total_percent += advance_payment.percent

        if total_amount is not None:
            for advance_payment in advance_payments:
                if advance_payment.percent is None:
                    continue
                line_amount = _calculate_advance_line_amount(
                    advance_payment, use_gross=use_gross
                )
                if line_amount is None:
                    continue
                expected_amount = (
                    total_amount * advance_payment.percent / Decimal("100.00")
                )
                if abs(line_amount - expected_amount) > self.tolerance:
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
