from decimal import Decimal
from typing import cast

from app.domain.entities.errors.checks import BaseCheckError, PaymentVatRatesDifferError
from app.domain.entities.single_supplier_fields import (
    AdvancePayment,
    AdvancePaymentsField,
    Payment,
    PaymentList,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .base import BaseCheck
from .deps import OptionalDep, Requires
from .errors import InsufficientCheckDataError


def _advance_has_any_vat_rate(adv: AdvancePayment) -> bool:
    if adv.total is not None and adv.total.vat.rate is not None:
        return True
    return bool(adv.payment_lines.vat_rates)


def _advances_field_has_any_vat_rate(
    advance_payments_field: AdvancePaymentsField | None,
) -> bool:
    if advance_payments_field is None or len(advance_payments_field.value) == 0:
        return False
    return any(_advance_has_any_vat_rate(adv) for adv in advance_payments_field.value)


def _filter_valid_payments(payments: PaymentList) -> PaymentList:
    return PaymentList(
        [payment for payment in payments if payment.vat.rate is not None]
    )


class CheckTaxRatesValidation(BaseCheck):
    total_amount_field = Requires(TotalAmountField)
    advance_payments_field = OptionalDep(AdvancePaymentsField)

    def __init__(self) -> None:
        self.errors: list[BaseCheckError] = []

    def _append_payment_lines_mismatch(
        self,
        reference_rate: Decimal | None,
        lines: PaymentList,
    ) -> None:
        for i, payment in enumerate(lines):
            if payment.vat.rate != reference_rate:
                self.errors.append(
                    PaymentVatRatesDifferError(
                        index=i,
                        rate_one=reference_rate,
                        rate_two=payment.vat.rate,
                    )
                )

    def _append_aggregate_rate_vs_contract(
        self,
        contract_rate: Decimal | None,
        aggregate: Payment | None,
        index: int | None = None,
    ) -> None:
        if aggregate is None or aggregate.vat.rate is None or contract_rate is None:
            return
        adv_rate = aggregate.vat.rate
        if contract_rate == adv_rate:
            return
        self.errors.append(
            PaymentVatRatesDifferError(
                index=index,
                rate_one=contract_rate,
                rate_two=adv_rate,
            )
        )

    def _append_aggregate_vs_reference(
        self,
        aggregate: Payment | None,
        contract_rate: Decimal | None,
        tax_rates: set[Decimal],
        index: int | None = None,
    ) -> None:
        if aggregate is None or aggregate.vat.rate is None:
            return
        rate = aggregate.vat.rate
        if tax_rates:
            if rate not in tax_rates:
                self.errors.append(
                    PaymentVatRatesDifferError(
                        index=index, rate_one=rate, rate_two=None
                    )
                )
            return
        self._append_aggregate_rate_vs_contract(contract_rate, aggregate, index=index)

    def _collect_advance_rate_errors(
        self,
        contract_rate: Decimal | None,
        tax_rates: set[Decimal],
        advance_payments: list[AdvancePayment],
    ) -> None:
        for i, advance_payment in enumerate(advance_payments):
            if not advance_payment.payments:
                self._append_aggregate_vs_reference(
                    advance_payment.total, contract_rate, tax_rates, index=i
                )
                continue

            valid_payments = _filter_valid_payments(
                PaymentList(advance_payment.payments),
            )

            advance_total_rate = (
                advance_payment.total.vat.rate
                if advance_payment.total is not None
                else None
            )
            if advance_total_rate is None:
                if tax_rates:
                    self.errors.extend(
                        PaymentVatRatesDifferError(
                            index=i,
                            rate_one=payment.vat.rate,
                            rate_two=None,
                        )
                        for payment in valid_payments
                        if payment.vat.rate not in tax_rates
                    )
                elif contract_rate is not None:
                    self._append_payment_lines_mismatch(
                        contract_rate,
                        valid_payments,
                    )
            else:
                self._append_aggregate_vs_reference(
                    advance_payment.total, contract_rate, tax_rates, index=i
                )
                self._append_payment_lines_mismatch(
                    advance_total_rate,
                    valid_payments,
                )

    async def execute(self) -> CheckExecutionResult:
        self.errors = []

        total_amount_field = cast("TotalAmountField", self.total_amount_field)
        advance_payments_field = cast(
            "AdvancePaymentsField | None", self.advance_payments_field
        )

        ta = total_amount_field.value
        taxes = ta.taxes

        if not (
            ta.total.vat.rate is not None
            or ta.taxes.vat_rates
            or _advances_field_has_any_vat_rate(advance_payments_field)
        ):
            raise InsufficientCheckDataError(
                self.__class__.__name__,
                "no VAT rates found in contract, taxes, or advances",
            )

        valid_taxes = _filter_valid_payments(taxes)

        if valid_taxes and ta.total.vat.rate is not None:
            self._append_payment_lines_mismatch(
                ta.total.vat.rate,
                valid_taxes,
            )

        if advance_payments_field is None or len(advance_payments_field.value) == 0:
            return self._result(self.errors)

        contract_rate = ta.total.vat.rate
        self._collect_advance_rate_errors(
            contract_rate, ta.taxes.vat_rates, advance_payments_field.value
        )
        return self._result(self.errors)
