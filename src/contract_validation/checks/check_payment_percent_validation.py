import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from app.domain.checks.base import BaseCheck
from app.domain.entities.validation_errors import (
    PaymentAmountPercentDiscrepancy,
    PaymentPercentSumDiscrepancyCheckResult,
)


if TYPE_CHECKING:
    from app.domain.entities.single_supplier import (
        AdvancePayment,
        AdvancePaymentsField,
        TotalAmountField,
    )
    from app.domain.entities.validation import BaseResultChecker, CheckExecutionResult


logger = logging.getLogger(__name__)


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
    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance

    async def execute(
        self,
        advance_payments_field: AdvancePaymentsField,
        total_amount_field: TotalAmountField,
    ) -> CheckExecutionResult:
        errors: list[BaseResultChecker] = []
        payments = advance_payments_field.value
        total_payment = total_amount_field.value.total
        total_amount = (
            total_payment.amount.value if total_payment.amount is not None else None
        )

        if total_amount is None:
            logger.info(
                "Contract total amount is missing: amount-vs-percent "
                "comparison skipped; percent sum check still runs "
                "when all percents are specified",
            )

        if not payments:
            logger.info("There are no payments, no interest check required")
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
                PaymentAmountPercentDiscrepancy(
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
                    PaymentPercentSumDiscrepancyCheckResult(total_percent=total_percent),
                )
        if errors:
            logger.warning("Errors in payment distribution were identified")
            return self._result(errors)

        logger.info("Test passed successfully")
        return self._result(errors)
