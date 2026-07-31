from decimal import Decimal

import pytest

from app.domain.checks.check_values_validation import CheckValuesValidation
from app.domain.entities import (
    AdvancePayment,
    AdvancePaymentList,
    AdvancePaymentsField,
    Money,
    Payment,
    PaymentList,
    Specification,
    SpecPosition,
    SpecPositionsField,
    TotalAmount,
    TotalAmountField,
    Vat,
    VatInclusion,
)
from app.domain.entities.errors.checks import (
    AmountNotPositiveError,
    VatAmountNotPositiveError,
    VatRateNotPositiveError,
)
from app.domain.entities.validation import CheckStatus


pytestmark = pytest.mark.asyncio


def _make_payment(
    *,
    amount: str | None = None,
    vat_amount: str | None = None,
    vat_rate: str | None = None,
) -> Payment:
    return Payment(
        amount=(
            Money(value=Decimal(amount), transcription=None)
            if amount is not None
            else None
        ),
        vat=Vat(
            amount=(
                Money(value=Decimal(vat_amount), transcription=None)
                if vat_amount is not None
                else None
            ),
            rate=Decimal(vat_rate) if vat_rate is not None else None,
        ),
        include_vat=VatInclusion.UNSPECIFIED,
    )


async def test_values_validation_succeeds_without_optional_fields() -> None:
    check = CheckValuesValidation()
    check.prepare([])

    result = await check.execute()

    assert result.status is CheckStatus.SUCCESS
    assert result.errors == []


async def test_values_validation_rejects_zero_amounts() -> None:
    total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_payment(amount="0"),
            taxes=PaymentList([]),
        ),
        sources=[],
    )
    spec_positions_field = SpecPositionsField(
        value=Specification(
            [
                SpecPosition(
                    name="Position",
                    quantity=Decimal(1),
                    unit_price=Decimal(0),
                    total_price=Decimal(0),
                    unit_of_measurement="piece",
                )
            ]
        ),
        sources=[],
    )
    check = CheckValuesValidation()
    check.prepare([total_amount_field, spec_positions_field])

    result = await check.execute()

    assert result.status is CheckStatus.FAILED
    assert result.errors == [
        AmountNotPositiveError(value=Decimal(0)),
        AmountNotPositiveError(value=Decimal(0)),
        AmountNotPositiveError(value=Decimal(0)),
    ]


async def test_values_validation_allows_zero_vat_amount() -> None:
    total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_payment(vat_amount="0"),
            taxes=PaymentList([]),
        ),
        sources=[],
    )
    check = CheckValuesValidation()
    check.prepare([total_amount_field])

    result = await check.execute()

    assert result.status is CheckStatus.SUCCESS
    assert result.errors == []


async def test_values_validation_collects_errors_from_all_models() -> None:
    total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_payment(amount="0", vat_amount="-2", vat_rate="-1"),
            taxes=PaymentList([]),
        ),
        sources=[],
    )
    advance_total = _make_payment(amount="-3")
    advance_payments_field = AdvancePaymentsField(
        value=AdvancePaymentList(
            [
                AdvancePayment(
                    percent=None,
                    amount=advance_total.amount,
                    vat=advance_total.vat,
                    include_vat=advance_total.include_vat,
                    payments=PaymentList(
                        [_make_payment(vat_amount="-5", vat_rate="-4")]
                    ),
                )
            ]
        ),
        sources=[],
    )
    spec_positions_field = SpecPositionsField(
        value=Specification(
            [
                SpecPosition(
                    name="Position",
                    quantity=Decimal(0),
                    unit_price=Decimal(-6),
                    total_price=Decimal(-7),
                    unit_of_measurement="piece",
                )
            ]
        ),
        sources=[],
    )
    check = CheckValuesValidation()
    check.prepare(
        [
            total_amount_field,
            advance_payments_field,
            spec_positions_field,
        ]
    )

    result = await check.execute()

    assert result.status is CheckStatus.FAILED
    assert result.errors == [
        AmountNotPositiveError(value=Decimal(0)),
        VatRateNotPositiveError(value=Decimal(-1)),
        VatAmountNotPositiveError(value=Decimal(-2)),
        AmountNotPositiveError(value=Decimal(-3)),
        VatRateNotPositiveError(value=Decimal(-4)),
        VatAmountNotPositiveError(value=Decimal(-5)),
        AmountNotPositiveError(value=Decimal(-6)),
        AmountNotPositiveError(value=Decimal(-7)),
    ]
