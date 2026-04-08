from decimal import Decimal

import pytest
from app.domain.entities.errors import (
    AmountNotPositiveError,
    VatAmountCalculationDiscrepancyError,
    VatAmountDiscrepancyError,
)

from app.domain.checks.check_taxes_validation import CheckTaxesValidation
from app.domain.entities.single_supplier_fields import (
    AdvancePayment,
    AdvancePaymentsField,
    Amount,
    Payment,
    TotalAmount,
    TotalAmountField,
    Vat,
)
from app.domain.entities.validation import CheckStatus


pytestmark = pytest.mark.asyncio

DEFAULT_TOLERANCE = Decimal("0.01")


def _make_payment(
    *,
    amount: str | None,
    vat_amount: str,
    vat_rate: str,
    include_vat: bool,
) -> Payment:
    amount_obj = (
        Amount(value=Decimal(amount), transcription=None)
        if amount is not None
        else None
    )
    return Payment(
        amount=amount_obj,
        vat=Vat(
            amount=Amount(value=Decimal(vat_amount), transcription=None),
            rate=Decimal(vat_rate),
        ),
        include_vat=include_vat,
    )


def _make_total_amount_field(
    *, total: Payment, taxes: list[Payment] | None
) -> TotalAmountField:
    return TotalAmountField(
        value=TotalAmount(total=total, taxes=taxes or []),
        sources=[],
    )


async def test_check_nds_succeeds_when_formula_and_sums_are_valid():
    check = CheckTaxesValidation(tolerance=DEFAULT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="20.00",
        vat_rate="20.00",
        include_vat=True,
    )
    taxes = [
        _make_payment(
            amount="120.00",
            vat_amount="20.00",
            vat_rate="20.00",
            include_vat=True,
        ),
    ]
    advances = [
        AdvancePayment(
            percent=Decimal("50.00"),
            total=_make_payment(
                amount="60.00",
                vat_amount="10.00",
                vat_rate="20.00",
                include_vat=True,
            ),
            payments=[
                _make_payment(
                    amount="60.00",
                    vat_amount="10.00",
                    vat_rate="20.00",
                    include_vat=True,
                ),
            ],
        ),
        AdvancePayment(
            percent=Decimal("50.00"),
            total=_make_payment(
                amount="60.00",
                vat_amount="10.00",
                vat_rate="20.00",
                include_vat=True,
            ),
            payments=[
                _make_payment(
                    amount="60.00",
                    vat_amount="10.00",
                    vat_rate="20.00",
                    include_vat=True,
                ),
            ],
        ),
    ]

    result = await check.execute(
        total_amount_field=_make_total_amount_field(total=total_payment, taxes=taxes),
        advance_payments_field=AdvancePaymentsField(value=advances, sources=[]),
    )

    assert result.status == CheckStatus.success
    assert result.errors == []


async def test_check_nds_fails_when_formula_is_incorrect():
    check = CheckTaxesValidation(tolerance=DEFAULT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="21.00",
        vat_rate="20.00",
        include_vat=True,
    )
    taxes = [
        _make_payment(
            amount="120.00",
            vat_amount="21.00",
            vat_rate="20.00",
            include_vat=True,
        ),
    ]

    result = await check.execute(
        total_amount_field=_make_total_amount_field(total=total_payment, taxes=taxes),
        advance_payments_field=None,
    )

    assert result.status == CheckStatus.failed
    assert any(
        isinstance(error, VatAmountCalculationDiscrepancyError)
        for error in result.errors
    )


async def test_check_nds_fails_when_total_and_taxes_vat_sums_differ():
    check = CheckTaxesValidation(tolerance=DEFAULT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="20.00",
        vat_rate="20.00",
        include_vat=True,
    )
    taxes = [
        _make_payment(
            amount="60.00",
            vat_amount="10.00",
            vat_rate="20.00",
            include_vat=True,
        ),
    ]

    result = await check.execute(
        total_amount_field=_make_total_amount_field(total=total_payment, taxes=taxes),
        advance_payments_field=None,
    )

    assert result.status == CheckStatus.failed
    assert any(isinstance(error, VatAmountDiscrepancyError) for error in result.errors)


async def test_check_nds_compares_sums_even_when_amount_is_missing():
    check = CheckTaxesValidation(tolerance=DEFAULT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="20.00",
        vat_rate="20.00",
        include_vat=True,
    )
    taxes = [
        _make_payment(
            amount="120.00",
            vat_amount="20.00",
            vat_rate="20.00",
            include_vat=True,
        ),
    ]
    advances = [
        AdvancePayment(
            percent=Decimal("100.00"),
            total=_make_payment(
                amount=None,
                vat_amount="20.00",
                vat_rate="20.00",
                include_vat=True,
            ),
            payments=[
                _make_payment(
                    amount=None,
                    vat_amount="20.00",
                    vat_rate="20.00",
                    include_vat=True,
                ),
            ],
        )
    ]

    result = await check.execute(
        total_amount_field=_make_total_amount_field(total=total_payment, taxes=taxes),
        advance_payments_field=AdvancePaymentsField(value=advances, sources=[]),
    )

    assert result.status == CheckStatus.success
    assert not any(
        isinstance(error, VatAmountCalculationDiscrepancyError)
        for error in result.errors
    )


async def test_check_nds_succeeds_when_vat_is_not_included_and_formula_is_correct():
    check = CheckTaxesValidation(tolerance=DEFAULT_TOLERANCE)
    total_payment = _make_payment(
        amount="100.00",
        vat_amount="20.00",
        vat_rate="20.00",
        include_vat=False,
    )
    taxes = [
        _make_payment(
            amount="100.00",
            vat_amount="20.00",
            vat_rate="20.00",
            include_vat=False,
        )
    ]

    result = await check.execute(
        total_amount_field=_make_total_amount_field(total=total_payment, taxes=taxes),
        advance_payments_field=None,
    )

    assert result.status == CheckStatus.success
    assert result.errors == []


async def test_check_nds_tolerance_allows_exactly_one_cent_difference():
    check = CheckTaxesValidation(tolerance=DEFAULT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="20.01",
        vat_rate="20.00",
        include_vat=True,
    )
    taxes = [
        _make_payment(
            amount="120.00",
            vat_amount="20.01",
            vat_rate="20.00",
            include_vat=True,
        )
    ]

    result = await check.execute(
        total_amount_field=_make_total_amount_field(total=total_payment, taxes=taxes),
        advance_payments_field=None,
    )

    assert result.status == CheckStatus.success
    assert not any(
        isinstance(error, VatAmountCalculationDiscrepancyError)
        for error in result.errors
    )


async def test_check_nds_tolerance_fails_when_difference_is_above_one_cent():
    check = CheckTaxesValidation(tolerance=DEFAULT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="20.02",
        vat_rate="20.00",
        include_vat=True,
    )
    taxes = [
        _make_payment(
            amount="120.00",
            vat_amount="20.02",
            vat_rate="20.00",
            include_vat=True,
        )
    ]

    result = await check.execute(
        total_amount_field=_make_total_amount_field(total=total_payment, taxes=taxes),
        advance_payments_field=None,
    )

    assert result.status == CheckStatus.failed
    assert any(
        isinstance(error, VatAmountCalculationDiscrepancyError)
        for error in result.errors
    )


async def test_check_nds_fails_when_amount_is_not_positive():
    check = CheckTaxesValidation(tolerance=DEFAULT_TOLERANCE)
    total_payment = _make_payment(
        amount="0.00",
        vat_amount="20.00",
        vat_rate="20.00",
        include_vat=True,
    )

    result = await check.execute(
        total_amount_field=_make_total_amount_field(total=total_payment, taxes=None),
        advance_payments_field=None,
    )

    assert result.status == CheckStatus.failed
    assert any(isinstance(error, AmountNotPositiveError) for error in result.errors)


async def test_check_nds_allows_zero_vat_amount():
    check = CheckTaxesValidation(tolerance=DEFAULT_TOLERANCE)
    total_payment = _make_payment(
        amount=None,
        vat_amount="0.00",
        vat_rate="20.00",
        include_vat=True,
    )

    result = await check.execute(
        total_amount_field=_make_total_amount_field(total=total_payment, taxes=None),
        advance_payments_field=None,
    )

    assert result.status == CheckStatus.success
    assert result.errors == []


async def test_check_nds_allows_zero_vat_rate():
    check = CheckTaxesValidation(tolerance=DEFAULT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="0.00",
        vat_rate="0.00",
        include_vat=True,
    )

    result = await check.execute(
        total_amount_field=_make_total_amount_field(total=total_payment, taxes=None),
        advance_payments_field=None,
    )

    assert result.status == CheckStatus.success
    assert result.errors == []


async def test_check_nds_ignores_empty_taxes_list():
    check = CheckTaxesValidation(tolerance=DEFAULT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="20.00",
        vat_rate="20.00",
        include_vat=True,
    )

    result = await check.execute(
        total_amount_field=_make_total_amount_field(total=total_payment, taxes=[]),
        advance_payments_field=None,
    )

    assert result.status == CheckStatus.success
    assert not any(
        isinstance(error, VatAmountDiscrepancyError) for error in result.errors
    )


async def test_check_nds_ignores_advances_without_totals_and_payments():
    check = CheckTaxesValidation(tolerance=DEFAULT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="20.00",
        vat_rate="20.00",
        include_vat=True,
    )
    advances = [
        AdvancePayment(percent=Decimal("50.00"), total=None, payments=[]),
        AdvancePayment(percent=Decimal("50.00"), total=None, payments=[]),
    ]

    result = await check.execute(
        total_amount_field=_make_total_amount_field(total=total_payment, taxes=None),
        advance_payments_field=AdvancePaymentsField(value=advances, sources=[]),
    )

    assert result.status == CheckStatus.success
    assert not any(
        isinstance(error, VatAmountDiscrepancyError) for error in result.errors
    )
