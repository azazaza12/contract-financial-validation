from decimal import Decimal

import pytest

from app.domain.checks.check_amounts_validation import CheckTotalAmountsValidation
from app.domain.checks.errors import InsufficientCheckDataError
from app.domain.constants import AMOUNT_TOLERANCE
from app.domain.entities import (
    EMPTY_PAYMENT,
    AdvancePayment,
    AdvancePaymentList,
    AdvancePaymentsField,
    AmountOperand,
    Money,
    Payment,
    PaymentList,
    TotalAmount,
    TotalAmountField,
    Vat,
    VatInclusion,
)
from app.domain.entities.errors import (
    AdvanceAmountDiscrepancyError,
    AdvanceVatAmountDiscrepancyError,
    TaxesAmountDiscrepancyError,
    TaxesVatAmountDiscrepancyError,
)
from app.domain.entities.validation import CheckStatus


pytestmark = pytest.mark.asyncio

TWO_ERRORS = 2


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


def _advance_payment(
    *, percent: Decimal | None, total: Payment | None
) -> AdvancePayment:
    base = total if total is not None else EMPTY_PAYMENT
    return AdvancePayment(
        percent=percent,
        amount=base.amount,
        vat=base.vat,
        include_vat=base.include_vat,
    )


def _make_total_amount_field(
    *,
    total_amount: str | None,
    taxes_amounts: list[str | None] | None,
) -> TotalAmountField:
    taxes = PaymentList([_make_payment(value) for value in taxes_amounts or []])
    return TotalAmountField(
        value=TotalAmount(
            total=_make_payment(total_amount),
            taxes=taxes,
        ),
        sources=[],
    )


async def _run_check(
    *,
    total_amount: str | None,
    taxes_amounts: list[str | None] | None,
    advances: list[AdvancePayment] | None,
):
    check = CheckTotalAmountsValidation(tolerance=AMOUNT_TOLERANCE)
    check.total_amount_field = _make_total_amount_field(
        total_amount=total_amount,
        taxes_amounts=taxes_amounts,
    )
    check.advance_payments_field = (
        AdvancePaymentsField(value=AdvancePaymentList(advances), sources=[])
        if advances is not None
        else None
    )
    return await check.execute()


async def _run_payments_check(
    *,
    total: Payment,
    taxes: list[Payment] | None = None,
    advances: list[AdvancePayment] | None = None,
):
    check = CheckTotalAmountsValidation(tolerance=AMOUNT_TOLERANCE)
    check.total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=total,
            taxes=PaymentList(taxes or []),
        ),
        sources=[],
    )
    check.advance_payments_field = (
        AdvancePaymentsField(value=AdvancePaymentList(advances), sources=[])
        if advances is not None
        else None
    )
    return await check.execute()


async def test_total_amounts_succeeds_when_total_taxes_and_advances_match() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=PaymentList(["100.00"]),
        advances=[
            _advance_payment(percent=Decimal("50.00"), total=_make_payment("50.00")),
            _advance_payment(percent=Decimal("50.00"), total=_make_payment("50.00")),
        ],
    )

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_total_amounts_fails_when_total_and_taxes_differ() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=PaymentList(["90.00"]),
        advances=None,
    )

    assert result.status == CheckStatus.FAILED
    assert any(isinstance(err, TaxesAmountDiscrepancyError) for err in result.errors)


async def test_total_amounts_skips_none_amounts_without_crash() -> None:
    with pytest.raises(InsufficientCheckDataError):
        await _run_check(
            total_amount=None,
            taxes_amounts=[None],
            advances=[
                _advance_payment(percent=None, total=None),
            ],
        )


async def test_total_amounts_tolerance_allows_difference_within_one_ruble() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=[str(Decimal("100.00") + AMOUNT_TOLERANCE - Decimal("0.01"))],
        advances=None,
    )

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_total_amounts_fails_when_tolerance_exceeded() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=[str(Decimal("100.00") + AMOUNT_TOLERANCE + Decimal("0.01"))],
        advances=None,
    )

    assert result.status == CheckStatus.FAILED
    assert any(isinstance(err, TaxesAmountDiscrepancyError) for err in result.errors)


async def test_total_amounts_succeeds_with_only_total_amount() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=None,
        advances=None,
    )

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_total_amounts_insufficient_with_only_taxes_amount() -> None:
    with pytest.raises(InsufficientCheckDataError):
        await _run_check(
            total_amount=None,
            taxes_amounts=["100.00"],
            advances=None,
        )


async def test_total_amounts_insufficient_with_only_advance_total() -> None:
    with pytest.raises(InsufficientCheckDataError):
        await _run_check(
            total_amount=None,
            taxes_amounts=None,
            advances=[
                _advance_payment(percent=None, total=_make_payment("100.00")),
            ],
        )


async def test_total_amounts_succeeds_with_only_total_vat_amount() -> None:
    check = CheckTotalAmountsValidation(tolerance=AMOUNT_TOLERANCE)
    check.total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=Payment(
                amount=None,
                vat=Vat(
                    amount=Money(value=Decimal("20.00"), transcription=None),
                    rate=Decimal("20.00"),
                ),
                include_vat=VatInclusion.INCLUDED,
            ),
            taxes=PaymentList([]),
        ),
        sources=[],
    )
    check.advance_payments_field = None

    result = await check.execute()

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_total_amounts_succeeds_when_taxes_list_is_empty() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=[],
        advances=None,
    )

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_total_amounts_succeeds_with_multiple_taxes_when_sum_matches_total() -> (
    None
):
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=["60.00", "40.00"],
        advances=None,
    )

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_total_amounts_succeeds_with_multiple_advances_summed() -> None:
    result = await _run_check(
        total_amount="300.00",
        taxes_amounts=["300.00"],
        advances=[
            _advance_payment(percent=Decimal("50.00"), total=_make_payment("150.00")),
            _advance_payment(percent=Decimal("50.00"), total=_make_payment("150.00")),
        ],
    )

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


# --- аванс с total ---


async def test_advance_with_only_total_matches_contract_success() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=None,
        advances=[
            _advance_payment(percent=None, total=_make_payment("100.00")),
        ],
    )
    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_advance_with_only_total_differs_from_contract_fails() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=None,
        advances=[
            _advance_payment(percent=None, total=_make_payment("90.00")),
        ],
    )
    assert result.status == CheckStatus.FAILED
    assert any(isinstance(err, AdvanceAmountDiscrepancyError) for err in result.errors)


# --- taxes с частичными None суммами ---


async def test_taxes_with_none_amount_skipped_in_sum() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=[None, "100.00"],
        advances=None,
    )
    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


# --- несколько ошибок за один прогон ---


async def test_errors_collected_from_multiple_sources() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=["90.00"],
        advances=[
            _advance_payment(percent=None, total=_make_payment("80.00")),
        ],
    )
    assert result.status == CheckStatus.FAILED
    assert len(result.errors) == TWO_ERRORS
    assert any(isinstance(err, TaxesAmountDiscrepancyError) for err in result.errors)
    assert any(isinstance(err, AdvanceAmountDiscrepancyError) for err in result.errors)


async def test_total_amounts_compares_total_and_taxes_vat_amounts() -> None:
    result = await _run_payments_check(
        total=_make_payment(None, vat_amount_value="20.00"),
        taxes=[_make_payment(None, vat_amount_value="10.00")],
    )

    assert result.status is CheckStatus.FAILED
    assert result.errors == [
        TaxesVatAmountDiscrepancyError(
            value=Decimal("10.00"),
            reference_value=Decimal("20.00"),
            difference=Decimal("10.00"),
        )
    ]


async def test_total_amounts_compares_vat_when_regular_amounts_are_missing() -> None:
    result = await _run_payments_check(
        total=_make_payment("120.00", vat_amount_value="20.00"),
        taxes=[_make_payment("120.00", vat_amount_value="20.00")],
        advances=[
            _advance_payment(
                percent=Decimal("100.00"),
                total=_make_payment(None, vat_amount_value="20.00"),
            )
        ],
    )

    assert result.status is CheckStatus.SUCCESS
    assert result.errors == []


async def test_total_amounts_sums_multiple_advance_total_vat_amounts() -> None:
    result = await _run_payments_check(
        total=_make_payment(None, vat_amount_value="20.00"),
        advances=[
            _advance_payment(
                percent=None, total=_make_payment(None, vat_amount_value="12.00")
            ),
            _advance_payment(
                percent=None, total=_make_payment(None, vat_amount_value="8.00")
            ),
        ],
    )

    assert result.status is CheckStatus.SUCCESS
    assert result.errors == []


async def test_total_amounts_detects_advance_total_vat_discrepancy() -> None:
    result = await _run_payments_check(
        total=_make_payment(None, vat_amount_value="20.00"),
        advances=[
            _advance_payment(
                percent=None, total=_make_payment(None, vat_amount_value="10.00")
            )
        ],
    )

    assert result.status is CheckStatus.FAILED
    assert result.errors == [
        AdvanceVatAmountDiscrepancyError(
            value=Decimal("10.00"),
            reference_value=Decimal("20.00"),
            difference=Decimal("10.00"),
        )
    ]


def _make_vat_payment(value: str, *, rate: str, include_vat: VatInclusion) -> Payment:
    return Payment(
        amount=Money(value=Decimal(value), transcription=None),
        vat=Vat(amount=None, rate=Decimal(rate)),
        include_vat=include_vat,
    )


async def test_total_amounts_succeeds_when_total_gross_and_tax_net_match() -> None:
    check = CheckTotalAmountsValidation(tolerance=AMOUNT_TOLERANCE)
    check.total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_vat_payment(
                "120.00", rate="20.00", include_vat=VatInclusion.INCLUDED
            ),
            taxes=PaymentList(
                [
                    _make_vat_payment(
                        "100.00", rate="20.00", include_vat=VatInclusion.EXCLUDED
                    )
                ]
            ),
        ),
        sources=[],
    )
    check.advance_payments_field = None

    result = await check.execute()

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_total_amounts_selects_basis_from_tax_items_and_total() -> None:
    result = await _run_payments_check(
        total=Payment(
            amount=Money(value=Decimal("200.00"), transcription=None),
            vat=Vat(amount=None, rate=None),
            include_vat=VatInclusion.EXCLUDED,
        ),
        taxes=[
            _make_vat_payment(
                "120.00",
                rate="20.00",
                include_vat=VatInclusion.INCLUDED,
            ),
            _make_vat_payment(
                "100.00",
                rate="10.00",
                include_vat=VatInclusion.EXCLUDED,
            ),
        ],
    )

    assert result.status is CheckStatus.SUCCESS
    assert result.errors == []


async def test_total_amounts_falls_back_to_raw_amounts_without_common_basis() -> None:
    result = await _run_payments_check(
        total=Payment(
            amount=Money(value=Decimal("100.00"), transcription=None),
            vat=Vat(amount=None, rate=None),
            include_vat=VatInclusion.EXCLUDED,
        ),
        taxes=[
            Payment(
                amount=Money(value=Decimal("120.00"), transcription=None),
                vat=Vat(amount=None, rate=None),
                include_vat=VatInclusion.INCLUDED,
            )
        ],
    )

    assert result.status is CheckStatus.FAILED
    assert result.errors == [
        TaxesAmountDiscrepancyError(
            value=Decimal("120.00"),
            reference_value=Decimal("100.00"),
            difference=Decimal("20.00"),
            target_inclusion=VatInclusion.MIXED,
            operands=(
                AmountOperand(
                    value=Decimal("120.00"),
                    vat_amount=None,
                    vat_rate=None,
                    vat_inclusion=VatInclusion.INCLUDED,
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


async def test_total_amounts_falls_back_to_raw_when_tax_lacks_rate() -> None:
    check = CheckTotalAmountsValidation(tolerance=AMOUNT_TOLERANCE)
    check.total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_vat_payment(
                "100.00", rate="20.00", include_vat=VatInclusion.EXCLUDED
            ),
            taxes=PaymentList([_make_payment("100.00")]),
        ),
        sources=[],
    )
    check.advance_payments_field = None

    result = await check.execute()

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_total_amounts_fails_when_grossed_amounts_differ() -> None:
    check = CheckTotalAmountsValidation(tolerance=AMOUNT_TOLERANCE)
    check.total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_vat_payment(
                "120.00", rate="20.00", include_vat=VatInclusion.INCLUDED
            ),
            taxes=PaymentList(
                [
                    _make_vat_payment(
                        "120.00", rate="20.00", include_vat=VatInclusion.EXCLUDED
                    )
                ]
            ),
        ),
        sources=[],
    )
    check.advance_payments_field = None

    result = await check.execute()

    assert result.status == CheckStatus.FAILED
    # total = 120.00 "в т.ч. НДС" (брутто), taxes = 120.00 "без НДС" (нетто);
    # на общей базе INCLUDED это 120.00 vs 144.00, а не 120.00 vs 120.00
    assert result.errors == [
        TaxesAmountDiscrepancyError(
            value=Decimal("144.00"),
            reference_value=Decimal("120.00"),
            difference=Decimal("24.00"),
            target_inclusion=VatInclusion.INCLUDED,
            operands=(
                AmountOperand(
                    value=Decimal("120.00"),
                    vat_amount=None,
                    vat_rate=Decimal("20.00"),
                    vat_inclusion=VatInclusion.EXCLUDED,
                ),
            ),
            reference_operand=AmountOperand(
                value=Decimal("120.00"),
                vat_amount=None,
                vat_rate=Decimal("20.00"),
                vat_inclusion=VatInclusion.INCLUDED,
            ),
        )
    ]


async def test_total_amounts_uses_excluding_vat_when_gross_unavailable() -> None:
    check = CheckTotalAmountsValidation(tolerance=AMOUNT_TOLERANCE)
    check.total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_vat_payment(
                "120.00", rate="20.00", include_vat=VatInclusion.INCLUDED
            ),
            taxes=PaymentList(
                [
                    Payment(
                        amount=Money(value=Decimal("100.00"), transcription=None),
                        vat=Vat(amount=None, rate=None),
                        include_vat=VatInclusion.EXCLUDED,
                    )
                ]
            ),
        ),
        sources=[],
    )
    check.advance_payments_field = None

    result = await check.execute()

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []
