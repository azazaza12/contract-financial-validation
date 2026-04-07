import logging
from decimal import Decimal

from app.domain.checks.base import BaseCheck
from app.domain.entities.single_supplier_fields import (
    AdvancePaymentsField,
    Payment,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult
from app.domain.entities.errors import (
    AmountNotPositiveError,
    BaseCheckError,
    VatAmountCalculationDiscrepancyError,
    VatAmountDiscrepancyError,
    VatAmountNotPositiveError,
    VatRateNotPositiveError,
)


logger = logging.getLogger(__name__)


class CheckTaxesValidation(BaseCheck):
    def __init__(self, tolerance: Decimal):
        self.tolerance = tolerance

    def check_vat_amounts_consistent(
        self, vat_amounts: list[Decimal], errors: list[BaseCheckError]
    ) -> None:
        if not vat_amounts:
            return
        reference_value = vat_amounts[0]
        for value in vat_amounts[1:]:
            difference = abs(value - reference_value)
            if difference > self.tolerance:
                errors.append(
                    VatAmountDiscrepancyError(
                        value=value,
                        reference_value=reference_value,
                        difference=difference,
                    )
                )

    def append_vat_from_total_amount(
        self,
        total_amount_field: TotalAmountField,
        vat_amounts: list[Decimal],
        errors: list[BaseCheckError],
    ) -> None:
        total_amount_payment = total_amount_field.value.total
        taxes = total_amount_field.value.taxes

        total_row_vat = self.validate_payments_and_sum_vat(
            [total_amount_payment], errors
        )
        if total_row_vat is not None:
            vat_amounts.append(total_row_vat)
        taxes_vat = self.validate_payments_and_sum_vat(taxes, errors)
        if taxes_vat is not None:
            vat_amounts.append(taxes_vat)

    def append_vat_from_advances(
        self,
        advance_payments_field: AdvancePaymentsField,
        vat_amounts: list[Decimal],
        errors: list[BaseCheckError],
    ) -> None:
        has_any = False
        advances_vat_total = Decimal("0.00")
        for advance_payment in advance_payments_field.value:
            advance_aggregate_vat = None
            if advance_payment.total is not None:
                advance_aggregate_vat = self.validate_payments_and_sum_vat(
                    [advance_payment.total], errors
                )
                has_any = True
            if advance_aggregate_vat is not None:
                advances_vat_total += advance_aggregate_vat

            advance_lines_vat = None
            if advance_payment.payments is not None:
                advance_lines_vat = self.validate_payments_and_sum_vat(
                    advance_payment.payments, errors
                )
            if advance_lines_vat is not None:
                has_any = True

            if advance_aggregate_vat is None or advance_lines_vat is None:
                continue
            diff = abs(advance_aggregate_vat - advance_lines_vat)
            if diff <= self.tolerance:
                continue
            errors.append(
                VatAmountDiscrepancyError(
                    reference_value=advance_aggregate_vat,
                    value=advance_lines_vat,
                    difference=diff,
                )
            )
        if not has_any:
            return
        vat_amounts.append(advances_vat_total)

    def validate_payments_and_sum_vat(
        self, payments: list[Payment] | None, errors: list[BaseCheckError]
    ) -> Decimal | None:
        vat_amount_sum = Decimal("0.00")
        if payments is None or len(payments) == 0:
            return None
        for payment in payments:
            amount = None
            vat_amount = None
            if payment.amount is not None:
                amount = payment.amount.value
                if amount <= 0:
                    errors.append(AmountNotPositiveError(value=amount))
                    continue
            if payment.vat.amount is not None:
                vat_amount = payment.vat.amount.value
                if vat_amount < 0:
                    errors.append(VatAmountNotPositiveError(value=vat_amount))
                    continue
            vat_rate = payment.vat.rate
            if vat_rate is not None and vat_rate < 0:
                errors.append(VatRateNotPositiveError(value=vat_rate))
                continue
            include_vat = payment.include_vat
            if amount is not None and vat_rate is not None and vat_amount is not None:
                if include_vat:
                    expected_vat_amount = amount * (vat_rate / (100 + vat_rate))
                else:
                    expected_vat_amount = amount * (vat_rate / 100)
                diff_vat_amount = abs(vat_amount - expected_vat_amount)
                if diff_vat_amount > self.tolerance:
                    errors.append(
                        VatAmountCalculationDiscrepancyError(
                            expected_vat_amount=expected_vat_amount,
                            vat_amount=vat_amount,
                            difference=diff_vat_amount,
                        )
                    )
            if vat_amount is not None:
                vat_amount_sum += vat_amount
        return vat_amount_sum

    async def execute(
        self,
        total_amount_field: TotalAmountField,
        advance_payments_field: AdvancePaymentsField | None,
    ) -> CheckExecutionResult:
        errors: list[BaseCheckError] = []
        vat_amounts_to_compare: list[Decimal] = []

        self.append_vat_from_total_amount(
            total_amount_field, vat_amounts_to_compare, errors
        )
        if advance_payments_field is not None:
            self.append_vat_from_advances(
                advance_payments_field, vat_amounts_to_compare, errors
            )

        self.check_vat_amounts_consistent(vat_amounts_to_compare, errors)

        return self._result(errors)
