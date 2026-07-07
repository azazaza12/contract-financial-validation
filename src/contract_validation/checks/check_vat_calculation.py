from decimal import Decimal
from typing import cast

from app.domain.entities.errors.checks import (
    BaseCheckError,
    VatAmountCalculationDiscrepancyError,
)
from app.domain.entities.single_supplier_fields import (
    AdvancePaymentsField,
    Payment,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .base import BaseCheck
from .deps import CheckServices, OptionalDep, Requires
from .errors import InsufficientCheckDataError


class CheckVatCalculation(BaseCheck):
    total_amount_field = Requires(TotalAmountField)
    advance_payments_field = OptionalDep(AdvancePaymentsField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance
        self.errors: list[BaseCheckError] = []

    @staticmethod
    def _all_payments(
        total_amount_field: TotalAmountField,
        advance_payments_field: AdvancePaymentsField | None,
    ) -> list[Payment]:
        payments: list[Payment] = [total_amount_field.value.total]
        if total_amount_field.value.taxes:
            payments.extend(total_amount_field.value.taxes)
        if advance_payments_field is not None:
            for advance_payment in advance_payments_field.value:
                if advance_payment.total is not None:
                    payments.append(advance_payment.total)
                payments.extend(advance_payment.payments)
        return payments

    @staticmethod
    def _has_calc_data(payments: list[Payment]) -> bool:
        return any(
            payment.amount_value is not None
            and payment.vat_amount_value is not None
            and payment.vat_rate is not None
            for payment in payments
        )

    def _validate_payment(self, payment: Payment) -> None:
        expected = payment.expected_vat_amount
        amount = payment.amount_value
        vat_amount = payment.vat_amount_value
        vat_rate = payment.vat_rate
        if (
            expected is not None
            and amount is not None
            and amount > 0
            and vat_amount is not None
            and vat_amount >= 0
            and vat_rate is not None
            and vat_rate >= 0
        ):
            diff = abs(vat_amount - expected)
            if diff > self.tolerance:
                self.errors.append(
                    VatAmountCalculationDiscrepancyError(
                        expected_vat_amount=expected,
                        vat_amount=vat_amount,
                        difference=diff,
                    )
                )

    async def execute(self, check_services: CheckServices) -> CheckExecutionResult:  # noqa: ARG002
        self.errors = []

        total_amount_field = cast("TotalAmountField", self.total_amount_field)
        advance_payments_field = cast(
            "AdvancePaymentsField | None",
            self.advance_payments_field,
        )

        payments = self._all_payments(total_amount_field, advance_payments_field)

        if not self._has_calc_data(payments):
            raise InsufficientCheckDataError(
                self.__class__.__name__,
                "no payments with amount, VAT amount and VAT rate to verify",
            )

        for payment in payments:
            self._validate_payment(payment)

        return self._result(self.errors)
