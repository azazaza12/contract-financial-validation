from decimal import Decimal
from typing import cast

from app.domain.checks.base import BaseCheck
from app.domain.entities.errors import (
    AmountNotPositiveError,
    BaseCheckError,
    VatAmountCalculationDiscrepancyError,
    VatAmountDiscrepancyError,
    VatAmountNotPositiveError,
    VatRateNotPositiveError,
)
from app.domain.entities.single_supplier_fields import (
    AdvancePayment,
    AdvancePaymentsField,
    Payment,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .deps import CheckServices, OptionalDep, Requires
from .errors import InsufficientCheckDataError


class CheckTaxesValidation(BaseCheck):
    total_amount_field = Requires(TotalAmountField)
    advance_payments_field = OptionalDep(AdvancePaymentsField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance

    def _check_vat_amounts_consistent(
        self, vat_amounts: list[Decimal]
    ) -> list[BaseCheckError]:
        if not vat_amounts:
            return []
        errors: list[BaseCheckError] = []
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
        return errors

    def _collect_total_amount_vat(
        self, total_amount_field: TotalAmountField
    ) -> tuple[list[BaseCheckError], list[Decimal]]:
        errors: list[BaseCheckError] = []
        vat_amounts: list[Decimal] = []

        total_errors, total_row_vat = self._validate_payment(
            total_amount_field.value.total
        )
        errors.extend(total_errors)
        if total_row_vat is not None:
            vat_amounts.append(total_row_vat)

        taxes_errors, taxes_vat = self._validate_payments_and_sum_vat(
            total_amount_field.value.taxes
        )
        errors.extend(taxes_errors)
        if taxes_vat is not None:
            vat_amounts.append(taxes_vat)

        return errors, vat_amounts

    def _process_advance(
        self, advance_payment: AdvancePayment
    ) -> tuple[list[BaseCheckError], Decimal | None]:
        errors: list[BaseCheckError] = []

        aggregate_vat: Decimal | None = None
        if advance_payment.total is not None:
            total_errors, aggregate_vat = self._validate_payment(advance_payment.total)
            errors.extend(total_errors)

        lines_errors, lines_vat = self._validate_payments_and_sum_vat(
            advance_payment.payments
        )
        errors.extend(lines_errors)

        if aggregate_vat is not None and lines_vat is not None:
            diff = abs(aggregate_vat - lines_vat)
            if diff > self.tolerance:
                errors.append(
                    VatAmountDiscrepancyError(
                        reference_value=aggregate_vat,
                        value=lines_vat,
                        difference=diff,
                    )
                )

        return errors, aggregate_vat if aggregate_vat is not None else lines_vat

    def _collect_advances_vat(
        self, advance_payments_field: AdvancePaymentsField
    ) -> tuple[list[BaseCheckError], Decimal | None]:
        errors: list[BaseCheckError] = []
        advances_vat_total: Decimal | None = None
        for advance_payment in advance_payments_field.value:
            adv_errors, vat_amount = self._process_advance(advance_payment)
            errors.extend(adv_errors)
            if vat_amount is not None:
                advances_vat_total = (
                    advances_vat_total or Decimal("0.00")
                ) + vat_amount
        return errors, advances_vat_total

    def _validate_payment(
        self, payment: Payment
    ) -> tuple[list[BaseCheckError], Decimal | None]:
        errors: list[BaseCheckError] = []
        amount = payment.amount.value if payment.amount is not None else None
        vat_amount = (
            payment.vat.amount.value if payment.vat.amount is not None else None
        )
        vat_rate = payment.vat.rate

        if amount is not None and amount <= 0:
            errors.append(AmountNotPositiveError(value=amount))
        if vat_amount is not None and vat_amount < 0:
            errors.append(VatAmountNotPositiveError(value=vat_amount))
        if vat_rate is not None and vat_rate < 0:
            errors.append(VatRateNotPositiveError(value=vat_rate))

        if (
            amount is not None
            and amount > 0
            and vat_amount is not None
            and vat_amount >= 0
            and vat_rate is not None
            and vat_rate >= 0
        ):
            if payment.include_vat:
                expected = amount * vat_rate / (100 + vat_rate)
            else:
                expected = amount * vat_rate / 100
            diff = abs(vat_amount - expected)
            if diff > self.tolerance:
                errors.append(
                    VatAmountCalculationDiscrepancyError(
                        expected_vat_amount=expected,
                        vat_amount=vat_amount,
                        difference=diff,
                    )
                )

        valid_vat = vat_amount if (vat_amount is not None and vat_amount >= 0) else None
        return errors, valid_vat

    def _validate_payments_and_sum_vat(
        self, payments: list[Payment] | None
    ) -> tuple[list[BaseCheckError], Decimal | None]:
        if not payments:
            return [], None
        errors: list[BaseCheckError] = []
        vat_sum: Decimal | None = None
        for payment in payments:
            p_errors, vat_amount = self._validate_payment(payment)
            errors.extend(p_errors)
            if vat_amount is not None:
                vat_sum = (vat_sum or Decimal("0.00")) + vat_amount
        return errors, vat_sum

    async def execute(self, _check_services: CheckServices) -> CheckExecutionResult:
        total_amount_field = cast("TotalAmountField", self.total_amount_field)
        advance_payments_field = cast(
            "AdvancePaymentsField | None",
            self.advance_payments_field,
        )
        errors: list[BaseCheckError] = []
        vat_amounts_to_compare: list[Decimal] = []

        total_errors, total_vat_amounts = self._collect_total_amount_vat(
            total_amount_field
        )
        errors.extend(total_errors)
        vat_amounts_to_compare.extend(total_vat_amounts)
        if advance_payments_field is not None:
            adv_errors, advances_vat = self._collect_advances_vat(
                advance_payments_field
            )
            errors.extend(adv_errors)
            if advances_vat is not None:
                vat_amounts_to_compare.append(advances_vat)

        if not vat_amounts_to_compare and not errors:
            raise InsufficientCheckDataError(
                self.__class__.__name__,
                "no VAT amounts found to validate",
            )
        errors.extend(self._check_vat_amounts_consistent(vat_amounts_to_compare))

        return self._result(errors)
