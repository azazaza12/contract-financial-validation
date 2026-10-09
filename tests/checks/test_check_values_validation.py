from decimal import Decimal
from uuid import uuid4

import pytest

from contract_validation.checks.check_values_validation import CheckValuesValidation
from contract_validation.entities import (
    AdvancePayment,
    AdvancePaymentList,
    AdvancePaymentsField,
    FieldLocation,
    Money,
    Payment,
    PaymentList,
    Source,
    SourceHeader,
    Specification,
    SpecPosition,
    SpecPositionsField,
    TotalAmount,
    TotalAmountField,
    Vat,
    VatInclusion,
)
from contract_validation.entities.errors.checks import (
    AmountNotFoundError,
    AmountNotPositiveError,
    VatAmountNotPositiveError,
    VatRateNotPositiveError,
)
from contract_validation.entities.validation import CheckStatus


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


async def test_values_validation_reports_missing_total_amount_field() -> None:
    check = CheckValuesValidation()
    check.prepare([])

    result = await check.execute()

    assert result.status is CheckStatus.FAILED
    assert result.errors == [AmountNotFoundError()]


async def test_values_validation_reports_missing_total_amount_when_only_vat_known() -> (
    None
):
    total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_payment(vat_amount="100", vat_rate="20"),
            taxes=PaymentList([]),
        ),
        sources=[],
    )
    check = CheckValuesValidation()
    check.prepare([total_amount_field])

    result = await check.execute()

    assert result.status is CheckStatus.FAILED
    assert result.errors == [AmountNotFoundError()]


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
        AmountNotPositiveError(
            value=Decimal(0),
            location=FieldLocation(
                field_name="TotalAmountField",
                path="value.total.amount.value",
                sources=(),
            ),
        ),
        AmountNotPositiveError(
            value=Decimal(0),
            location=FieldLocation(
                field_name="SpecPositionsField",
                path="value._positions[0].unit_price",
                sources=(),
            ),
        ),
        AmountNotPositiveError(
            value=Decimal(0),
            location=FieldLocation(
                field_name="SpecPositionsField",
                path="value._positions[0].total_price",
                sources=(),
            ),
        ),
    ]


async def test_values_validation_allows_zero_vat_amount() -> None:
    total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_payment(amount="1", vat_amount="0"),
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
    advance_total = _make_payment(amount="-3", vat_amount="-5", vat_rate="-4")
    advance_payments_field = AdvancePaymentsField(
        value=AdvancePaymentList(
            [
                AdvancePayment(
                    percent=None,
                    amount=advance_total.amount,
                    vat=advance_total.vat,
                    include_vat=advance_total.include_vat,
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
        AmountNotPositiveError(
            value=Decimal(0),
            location=FieldLocation(
                field_name="TotalAmountField",
                path="value.total.amount.value",
                sources=(),
            ),
        ),
        VatRateNotPositiveError(value=Decimal(-1)),
        VatAmountNotPositiveError(
            value=Decimal(-2),
            location=FieldLocation(
                field_name="TotalAmountField",
                path="value.total.vat.amount.value",
                sources=(),
            ),
        ),
        AmountNotPositiveError(
            value=Decimal(-3),
            location=FieldLocation(
                field_name="AdvancePaymentsField",
                path="value._payments[0].amount.value",
                sources=(),
            ),
        ),
        VatRateNotPositiveError(value=Decimal(-4)),
        VatAmountNotPositiveError(
            value=Decimal(-5),
            location=FieldLocation(
                field_name="AdvancePaymentsField",
                path="value._payments[0].vat.amount.value",
                sources=(),
            ),
        ),
        AmountNotPositiveError(
            value=Decimal(-6),
            location=FieldLocation(
                field_name="SpecPositionsField",
                path="value._positions[0].unit_price",
                sources=(),
            ),
        ),
        AmountNotPositiveError(
            value=Decimal(-7),
            location=FieldLocation(
                field_name="SpecPositionsField",
                path="value._positions[0].total_price",
                sources=(),
            ),
        ),
    ]


async def test_values_validation_identifies_payments_with_different_vat_rates() -> None:
    field_source = Source(document_id=uuid4(), header=SourceHeader.BODY)
    total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_payment(amount="100"),
            taxes=PaymentList(
                [
                    _make_payment(amount="-20", vat_amount="-4", vat_rate="20"),
                    _make_payment(amount="-10", vat_amount="-1", vat_rate="10"),
                ]
            ),
        ),
        sources=[field_source],
    )
    check = CheckValuesValidation()
    check.prepare([total_amount_field])

    result = await check.execute()

    assert [error.location.full_path for error in result.errors if error.location] == [
        "TotalAmountField.value.taxes._payments[0].amount.value",
        "TotalAmountField.value.taxes._payments[0].vat.amount.value",
        "TotalAmountField.value.taxes._payments[1].amount.value",
        "TotalAmountField.value.taxes._payments[1].vat.amount.value",
    ]
    assert all(
        error.location is not None and error.location.sources == (field_source,)
        for error in result.errors
    )
