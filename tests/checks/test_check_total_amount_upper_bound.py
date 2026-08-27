from decimal import Decimal

import pytest

from app.domain.checks.check_total_amount_upper_bound import (
    CheckTotalAmountUpperBound,
)
from app.domain.constants import AMOUNT_TOLERANCE
from app.domain.entities import (
    AmountOperand,
    Money,
    Payment,
    PaymentList,
    TotalAmount,
    TotalAmountField,
    TotalAmountUpperBoundField,
    Vat,
    VatInclusion,
)
from app.domain.entities.errors import UpperBoundAmountError, UpperBoundVatAmountError
from app.domain.entities.validation import CheckStatus


pytestmark = pytest.mark.asyncio


def _make_payment(
    amount_value: str | None,
    *,
    vat_amount_value: str | None = None,
) -> Payment:
    amount = (
        Money(value=Decimal(amount_value), transcription=None)
        if amount_value is not None
        else None
    )
    vat_amount = (
        Money(value=Decimal(vat_amount_value), transcription=None)
        if vat_amount_value is not None
        else None
    )
    return Payment(
        amount=amount,
        vat=Vat(amount=vat_amount, rate=None),
        include_vat=VatInclusion.EXCLUDED,
    )


async def _run_check(
    *,
    total_amount: str | None,
    total_vat_amount: str | None = None,
    bound_amount: str | None,
    bound_vat_amount: str | None = None,
):
    check = CheckTotalAmountUpperBound(tolerance=AMOUNT_TOLERANCE)
    check.total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_payment(total_amount, vat_amount_value=total_vat_amount),
            taxes=PaymentList([]),
        ),
        sources=[],
    )
    check.upper_bound_amount_field = TotalAmountUpperBoundField(
        value=TotalAmount(
            total=_make_payment(bound_amount, vat_amount_value=bound_vat_amount),
            taxes=PaymentList([]),
        ),
        sources=[],
    )
    return await check.execute()


async def test_upper_bound_succeeds_when_amount_below_bound() -> None:
    result = await _run_check(total_amount="90.00", bound_amount="100.00")

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_upper_bound_succeeds_when_amount_equals_bound() -> None:
    result = await _run_check(total_amount="100.00", bound_amount="100.00")

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_upper_bound_succeeds_when_excess_within_tolerance() -> None:
    result = await _run_check(
        total_amount=str(Decimal("100.00") + AMOUNT_TOLERANCE),
        bound_amount="100.00",
    )

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_upper_bound_fails_when_tolerance_exceeded() -> None:
    result = await _run_check(
        total_amount=str(Decimal("100.00") + AMOUNT_TOLERANCE + Decimal("0.01")),
        bound_amount="100.00",
    )

    assert result.status == CheckStatus.FAILED
    assert result.errors == [
        UpperBoundAmountError(
            value=Decimal("101.01"),
            bound_value=Decimal("100.00"),
            violation_value=Decimal("1.01"),
            target_inclusion=VatInclusion.EXCLUDED,
            operands=(
                AmountOperand(
                    value=Decimal("101.01"),
                    vat_amount=None,
                    vat_rate=None,
                    vat_inclusion=VatInclusion.EXCLUDED,
                ),
            ),
            reference_operand=AmountOperand(
                value=Decimal("100.00"),
                vat_amount=None,
                vat_rate=None,
                vat_inclusion=VatInclusion.EXCLUDED,
            ),
        )
    ]


async def test_upper_bound_fails_on_vat_amount_excess() -> None:
    result = await _run_check(
        total_amount="100.00",
        total_vat_amount="25.00",
        bound_amount="100.00",
        bound_vat_amount="20.00",
    )

    assert result.status == CheckStatus.FAILED
    assert result.errors == [
        UpperBoundVatAmountError(
            value=Decimal("25.00"),
            bound_value=Decimal("20.00"),
            violation_value=Decimal("5.00"),
        )
    ]
