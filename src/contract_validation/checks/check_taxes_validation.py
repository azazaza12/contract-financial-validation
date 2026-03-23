import logging
from decimal import Decimal
from app.domain.entities.validation import CheckExecutionResult, BaseResultChecker
from app.domain.entities.single_supplier import (
    TotalAmountField,
    AdvancePaymentsField,
    Payment,
)
from app.domain.entities.validation_errors import (
    VatAmountDiscrepancy,
    VatAmountCalculationDiscrepancy,
    VatAmountNotPositiveCheckResult,
    VatRateNotPositiveCheckResult,
    AmountNotPositiveCheckResult,
)
from app.domain.checks.base import BaseCheck


logger = logging.getLogger(__name__)


class CheckTaxesValidation(BaseCheck):
    def __init__(self, tolerance: Decimal | None = None):
        if tolerance is None:
            from app.config import ValidationSettings

            tolerance = ValidationSettings().AMOUNT_TOLERANCE
        self.tolerance = tolerance

    def check_vat_amounts_consistent(
        self, vat_amounts: list[Decimal], errors: list[BaseResultChecker]
    ) -> None:
        if not vat_amounts:
            return
        reference_value = vat_amounts[0]
        for value in vat_amounts[1:]:
            difference = abs(value - reference_value)
            if difference > self.tolerance:
                errors.append(
                    VatAmountDiscrepancy(
                        value=value,
                        reference_value=reference_value,
                        difference=difference,
                    )
                )

    def append_vat_from_total_amount(
        self,
        total_amount_field: TotalAmountField,
        vat_amounts: list[Decimal],
        errors: list[BaseResultChecker],
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
        errors: list[BaseResultChecker],
    ) -> None:
        has_any = False
        advances_vat_total = Decimal("0.00")
        for adv in advance_payments_field.value:
            advance_aggregate_vat = None
            if adv.total is not None:
                advance_aggregate_vat = self.validate_payments_and_sum_vat(
                    [adv.total], errors
                )
                has_any = True
            if advance_aggregate_vat is not None:
                advances_vat_total += advance_aggregate_vat

            advance_lines_vat = None
            if adv.payments is not None:
                advance_lines_vat = self.validate_payments_and_sum_vat(
                    adv.payments, errors
                )
            if advance_lines_vat is not None:
                has_any = True

            if advance_aggregate_vat is not None and advance_lines_vat is not None:
                diff = abs(advance_aggregate_vat - advance_lines_vat)
                if diff > self.tolerance:
                    errors.append(
                        VatAmountDiscrepancy(
                            reference_value=advance_aggregate_vat,
                            value=advance_lines_vat,
                            difference=diff,
                        )
                    )
        if has_any:
            vat_amounts.append(advances_vat_total)

    def validate_payments_and_sum_vat(
        self, payments: list[Payment] | None, errors: list[BaseResultChecker]
    ) -> Decimal | None:
        vat_amount_sum = Decimal("0.00")
        if payments is None:
            return None
        for payment in payments:
            amount = None
            vat_amount = None
            if payment.amount is not None:
                amount = payment.amount.value
                if amount <= 0:
                    errors.append(AmountNotPositiveCheckResult(value=amount))
                    continue
            if payment.vat.amount is not None:
                vat_amount = payment.vat.amount.value
                if vat_amount < 0:
                    errors.append(VatAmountNotPositiveCheckResult(value=vat_amount))
                    continue
            vat_rate = payment.vat.rate
            if vat_rate is not None and vat_rate < 0:
                errors.append(VatRateNotPositiveCheckResult(value=vat_rate))
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
                        VatAmountCalculationDiscrepancy(
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
        errors: list[BaseResultChecker] = []
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
