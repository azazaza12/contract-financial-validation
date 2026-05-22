from typing import TYPE_CHECKING, cast

from app.domain.checks.base import BaseCheck
from app.domain.entities.errors import (
    BaseCheckError,
    PaymentVatRateNotFoundError,
    PaymentVatRatesDifferError,
)
from app.domain.entities.single_supplier_fields import (
    AdvancePayment,
    AdvancePaymentsField,
    Payment,
    TotalAmount,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .deps import CheckServices, OptionalDep, Requires


if TYPE_CHECKING:
    from decimal import Decimal


def _payment_lines_mismatch_vs_reference(
    reference_rate: Decimal | None,
    lines: list[Payment],
) -> PaymentVatRatesDifferError | None:
    for payment in lines:
        line_rate = payment.vat.rate
        if line_rate != reference_rate:
            return PaymentVatRatesDifferError(
                index=None,
                rate_one=reference_rate,
                rate_two=line_rate,
            )
    return None


def _total_amount_has_any_vat_rate(ta: TotalAmount) -> bool:
    if ta.total.vat.rate is not None:
        return True
    taxes = ta.taxes
    if taxes:
        return any(p.vat.rate is not None for p in taxes)
    return False


def _advance_has_any_vat_rate(adv: AdvancePayment) -> bool:
    if adv.total is not None and adv.total.vat.rate is not None:
        return True
    if adv.payments:
        return any(p.vat.rate is not None for p in adv.payments)
    return False


def _advances_field_has_any_vat_rate(
    advance_payments_field: AdvancePaymentsField | None,
) -> bool:
    if advance_payments_field is None or len(advance_payments_field.value) == 0:
        return False
    return any(_advance_has_any_vat_rate(adv) for adv in advance_payments_field.value)


def _aggregate_rate_vs_contract(
    contract_rate: Decimal | None,
    aggregate: Payment | None,
) -> PaymentVatRatesDifferError | None:
    if aggregate is None:
        return None
    adv_rate = aggregate.vat.rate
    if contract_rate == adv_rate:
        return None
    return PaymentVatRatesDifferError(
        index=None,
        rate_one=contract_rate,
        rate_two=adv_rate,
    )


class CheckTaxRatesValidation(BaseCheck):
    total_amount_field = Requires(TotalAmountField)
    advance_payments_field = OptionalDep(AdvancePaymentsField)

    def _collect_advance_rate_errors(
        self, contract_rate: Decimal | None
    ) -> list[BaseCheckError]:
        errors = []
        for advance_payment in self.advance_payments_field.value:
            if not advance_payment.payments:
                mismatch = _aggregate_rate_vs_contract(
                    contract_rate,
                    advance_payment.total,
                )
                if mismatch is not None:
                    errors.append(mismatch)
                    return errors
                continue
            advance_total_rate = (
                advance_payment.total and advance_payment.total.vat.rate
            )
            if advance_total_rate is None:
                continue

            mismatch = _payment_lines_mismatch_vs_reference(
                advance_total_rate,
                advance_payment.payments,
            )
            if mismatch is None:
                continue
            errors.append(mismatch)
            return errors
        return errors

    async def execute(self, check_services: CheckServices) -> CheckExecutionResult:
        self.total_amount_field = cast("TotalAmountField", self.total_amount_field)
        self.advance_payments_field = cast(
            "AdvancePaymentsField | None",
            self.advance_payments_field,
        )
        errors: list[BaseCheckError] = []
        ta = self.total_amount_field.value
        taxes = ta.taxes

        if not (
            _total_amount_has_any_vat_rate(ta)
            or _advances_field_has_any_vat_rate(self.advance_payments_field)
        ):
            errors.append(PaymentVatRateNotFoundError())
            return self._result(errors)

        if taxes is not None and len(taxes) > 0:
            total_rate = ta.total.vat.rate
            if total_rate is not None:
                mismatch = _payment_lines_mismatch_vs_reference(total_rate, taxes)
                if mismatch is not None:
                    errors.append(mismatch)
                    return self._result(errors)

        if (
            self.advance_payments_field is None
            or len(self.advance_payments_field.value) == 0
        ):
            return self._result(errors)

        contract_rate = ta.total.vat.rate
        errors.extend(self._collect_advance_rate_errors(contract_rate))
        return self._result(errors)
