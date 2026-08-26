from decimal import Decimal

import pytest

from app.domain.checks.check_vat_calculation import CheckVatCalculation
from app.domain.checks.errors import InsufficientCheckDataError
from app.domain.constants import AMOUNT_TOLERANCE
from app.domain.entities import (
    EMPTY_PAYMENT,
    AdvancePayment,
    AdvancePaymentList,
    AdvancePaymentsField,
    Money,
    Payment,
    PaymentList,
    TotalAmount,
    TotalAmountField,
    Vat,
    VatInclusion,
)
from app.domain.entities.errors import VatAmountCalculationDiscrepancyError
from app.domain.entities.validation import CheckStatus


def _pay(
    *,
    amount: str | None,
    vat_amount: str | None,
    vat_rate: str | None,
    include_vat: VatInclusion,
) -> Payment:
    return Payment(
        amount=Money(value=Decimal(amount), transcription=None)
        if amount is not None
        else None,
        vat=Vat(
            amount=Money(value=Decimal(vat_amount), transcription=None)
            if vat_amount is not None
            else None,
            rate=Decimal(vat_rate) if vat_rate is not None else None,
        ),
        include_vat=include_vat,
    )


def _advance(*, percent: Decimal | None, total: Payment | None) -> AdvancePayment:
    base = total if total is not None else EMPTY_PAYMENT
    return AdvancePayment(
        percent=percent,
        amount=base.amount,
        vat=base.vat,
        include_vat=base.include_vat,
    )


def _make_total_amount_field(
    *,
    total: Payment,
    taxes: list[Payment] | None = None,
) -> TotalAmountField:
    return TotalAmountField(
        value=TotalAmount(total=total, taxes=PaymentList(taxes or [])),
        sources=[],
    )


async def _run(
    *,
    total: Payment,
    taxes: list[Payment] | None = None,
    advances: list[AdvancePayment] | None = None,
    tolerance: Decimal = AMOUNT_TOLERANCE,
):
    check = CheckVatCalculation(tolerance=tolerance)
    check.total_amount_field = _make_total_amount_field(total=total, taxes=taxes or [])
    check.advance_payments_field = (
        AdvancePaymentsField(value=AdvancePaymentList(advances), sources=[])
        if advances is not None
        else None
    )
    return await check.execute()


async def test_vat_calculation_succeeds_when_amount_includes_vat() -> None:
    r = await _run(
        total=_pay(
            amount="120.00",
            vat_amount="20.00",
            vat_rate="20.00",
            include_vat=VatInclusion.INCLUDED,
        ),
        taxes=[
            _pay(
                amount="120.00",
                vat_amount="20.00",
                vat_rate="20.00",
                include_vat=VatInclusion.INCLUDED,
            )
        ],
    )
    assert r.status == CheckStatus.SUCCESS
    assert r.errors == []


async def test_vat_calculation_succeeds_when_amount_excludes_vat() -> None:
    r = await _run(
        total=_pay(
            amount="100.00",
            vat_amount="20.00",
            vat_rate="20.00",
            include_vat=VatInclusion.EXCLUDED,
        ),
    )
    assert r.status == CheckStatus.SUCCESS
    assert r.errors == []


async def test_vat_calculation_fails_when_formula_is_incorrect() -> None:
    bad_vat = str(Decimal("20.00") + AMOUNT_TOLERANCE + Decimal("0.01"))
    r = await _run(
        total=_pay(
            amount="120.00",
            vat_amount=bad_vat,
            vat_rate="20.00",
            include_vat=VatInclusion.INCLUDED,
        ),
    )
    assert r.status == CheckStatus.FAILED
    assert any(isinstance(e, VatAmountCalculationDiscrepancyError) for e in r.errors)


async def test_vat_calculation_tolerance_allows_difference_within_one_ruble() -> None:
    within = str(Decimal("20.00") + AMOUNT_TOLERANCE - Decimal("0.01"))
    r = await _run(
        total=_pay(
            amount="120.00",
            vat_amount=within,
            vat_rate="20.00",
            include_vat=VatInclusion.INCLUDED,
        ),
    )
    assert r.status == CheckStatus.SUCCESS
    assert not any(
        isinstance(e, VatAmountCalculationDiscrepancyError) for e in r.errors
    )


async def test_vat_calculation_tolerance_fails_when_difference_exceeds_one_ruble() -> (
    None
):
    over = str(Decimal("20.00") + AMOUNT_TOLERANCE + Decimal("0.01"))
    r = await _run(
        total=_pay(
            amount="120.00",
            vat_amount=over,
            vat_rate="20.00",
            include_vat=VatInclusion.INCLUDED,
        ),
    )
    assert r.status == CheckStatus.FAILED
    assert any(isinstance(e, VatAmountCalculationDiscrepancyError) for e in r.errors)


async def test_vat_calculation_allows_zero_vat_rate() -> None:
    r = await _run(
        total=_pay(
            amount="120.00",
            vat_amount="0.00",
            vat_rate="0.00",
            include_vat=VatInclusion.INCLUDED,
        ),
    )
    assert r.status == CheckStatus.SUCCESS
    assert r.errors == []


async def test_vat_calculation_verifies_taxes() -> None:
    bad_vat = str(Decimal("20.00") + AMOUNT_TOLERANCE + Decimal("0.01"))
    r = await _run(
        total=_pay(
            amount="120.00",
            vat_amount="20.00",
            vat_rate="20.00",
            include_vat=VatInclusion.INCLUDED,
        ),
        taxes=[
            _pay(
                amount="120.00",
                vat_amount=bad_vat,
                vat_rate="20.00",
                include_vat=VatInclusion.INCLUDED,
            )
        ],
    )
    assert r.status == CheckStatus.FAILED
    assert any(isinstance(e, VatAmountCalculationDiscrepancyError) for e in r.errors)


async def test_vat_calculation_verifies_advance_total() -> None:
    bad_vat = str(Decimal("10.00") + AMOUNT_TOLERANCE + Decimal("0.01"))
    r = await _run(
        total=_pay(
            amount="120.00",
            vat_amount="20.00",
            vat_rate="20.00",
            include_vat=VatInclusion.INCLUDED,
        ),
        advances=[
            _advance(
                percent=None,
                total=_pay(
                    amount="60.00",
                    vat_amount=bad_vat,
                    vat_rate="20.00",
                    include_vat=VatInclusion.INCLUDED,
                ),
            ),
        ],
    )
    assert r.status == CheckStatus.FAILED
    assert any(isinstance(e, VatAmountCalculationDiscrepancyError) for e in r.errors)


async def test_vat_calculation_skipped_when_no_amount_vat_rate_data() -> None:
    check = CheckVatCalculation(tolerance=AMOUNT_TOLERANCE)
    check.total_amount_field = _make_total_amount_field(
        total=_pay(
            amount="120.00",
            vat_amount=None,
            vat_rate=None,
            include_vat=VatInclusion.INCLUDED,
        ),
    )
    check.advance_payments_field = None
    with pytest.raises(InsufficientCheckDataError):
        await check.execute()


async def test_vat_calculation_flags_mismatch_with_zero_amount() -> None:
    r = await _run(
        total=_pay(
            amount="0.00",
            vat_amount="20.00",
            vat_rate="20.00",
            include_vat=VatInclusion.INCLUDED,
        ),
    )
    assert r.status == CheckStatus.FAILED
    assert any(isinstance(e, VatAmountCalculationDiscrepancyError) for e in r.errors)


async def test_vat_calculation_succeeds_with_zero_amount_and_zero_vat() -> None:
    r = await _run(
        total=_pay(
            amount="0.00",
            vat_amount="0.00",
            vat_rate="20.00",
            include_vat=VatInclusion.INCLUDED,
        ),
    )
    assert r.status == CheckStatus.SUCCESS
    assert r.errors == []
