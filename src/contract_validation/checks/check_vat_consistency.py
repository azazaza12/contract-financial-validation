from decimal import Decimal
from typing import cast

from app.domain.entities.errors.checks import (
    AmountNotPositiveError,
    BaseCheckError,
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

from .base import BaseCheck
from .deps import CheckServices, OptionalDep, Requires
from .errors import InsufficientCheckDataError


class CheckVatConsistency(BaseCheck):
    total_amount_field = Requires(TotalAmountField)
    advance_payments_field = OptionalDep(AdvancePaymentsField)

    def __init__(self, tolerance: Decimal) -> None:
        self.tolerance = tolerance
        self.errors: list[BaseCheckError] = []
        self.vat_amounts: list[Decimal] = []

    def _check_vat_amounts_consistent(self) -> None:
        if not self.vat_amounts:
            return
        reference_value = self.vat_amounts[0]
        for value in self.vat_amounts[1:]:
            difference = abs(value - reference_value)
            if difference > self.tolerance:
                self.errors.append(
                    VatAmountDiscrepancyError(
                        value=value,
                        reference_value=reference_value,
                        difference=difference,
                    )
                )

    def _collect_total_amount_vat(self, total_amount_field: TotalAmountField) -> None:
        total_row_vat = self._valid_vat(total_amount_field.value.total)
        if total_row_vat is not None:
            self.vat_amounts.append(total_row_vat)

        taxes_vat = self._sum_valid_vat(total_amount_field.value.taxes)
        if taxes_vat is not None:
            self.vat_amounts.append(taxes_vat)

    def _process_advance(self, advance_payment: AdvancePayment) -> Decimal | None:
        aggregate_vat: Decimal | None = None
        if advance_payment.total is not None:
            aggregate_vat = self._valid_vat(advance_payment.total)

        lines_vat = self._sum_valid_vat(advance_payment.payments)

        if aggregate_vat is not None and lines_vat is not None:
            diff = abs(aggregate_vat - lines_vat)
            if diff > self.tolerance:
                self.errors.append(
                    VatAmountDiscrepancyError(
                        reference_value=aggregate_vat,
                        value=lines_vat,
                        difference=diff,
                    )
                )

        return aggregate_vat if aggregate_vat is not None else lines_vat

    def _collect_advances_vat(
        self, advance_payments_field: AdvancePaymentsField
    ) -> None:
        advances_vat_total: Decimal | None = None
        for advance_payment in advance_payments_field.value:
            vat_amount = self._process_advance(advance_payment)
            if vat_amount is not None:
                advances_vat_total = (
                    advances_vat_total or Decimal("0.00")
                ) + vat_amount
        if advances_vat_total is not None:
            self.vat_amounts.append(advances_vat_total)

    def _valid_vat(self, payment: Payment) -> Decimal | None:
        amount = payment.amount_value
        vat_amount = payment.vat_amount_value
        vat_rate = payment.vat_rate

        if amount is not None and amount <= 0:
            self.errors.append(AmountNotPositiveError(value=amount))
            amount = None
        if vat_amount is not None and vat_amount < 0:
            self.errors.append(VatAmountNotPositiveError(value=vat_amount))
            vat_amount = None
        if vat_rate is not None and vat_rate < 0:
            self.errors.append(VatRateNotPositiveError(value=vat_rate))
            vat_rate = None

        return vat_amount if (vat_amount is not None and vat_amount >= 0) else None

    def _sum_valid_vat(self, payments: list[Payment] | None) -> Decimal | None:
        if not payments:
            return None
        vat_sum: Decimal | None = None
        for payment in payments:
            vat_amount = self._valid_vat(payment)
            if vat_amount is not None:
                vat_sum = (vat_sum or Decimal("0.00")) + vat_amount
        return vat_sum

    async def execute(self, check_services: CheckServices) -> CheckExecutionResult:  # noqa: ARG002
        self.errors = []
        self.vat_amounts = []

        total_amount_field = cast("TotalAmountField", self.total_amount_field)
        advance_payments_field = cast(
            "AdvancePaymentsField | None",
            self.advance_payments_field,
        )

        self._collect_total_amount_vat(total_amount_field)
        if advance_payments_field is not None:
            self._collect_advances_vat(advance_payments_field)

        if not self.vat_amounts and not self.errors:
            raise InsufficientCheckDataError(
                self.__class__.__name__,
                "no VAT amounts found to validate",
            )
        self._check_vat_amounts_consistent()

        return self._result(self.errors)
