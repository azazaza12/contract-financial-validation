from decimal import Decimal

import pytest

from app.domain.checks.check_amounts_validation import CheckTotalAmountsValidation
from app.domain.checks.errors import InsufficientCheckDataError
from app.domain.constants import AMOUNT_TOLERANCE
from app.domain.entities import (
    AdvancePayment,
    AdvancePaymentsField,
    Amount,
    Payment,
    TotalAmount,
    TotalAmountField,
    Vat,
)
from app.domain.entities.errors import AmountDiscrepancyError
from app.domain.entities.validation import CheckStatus


pytestmark = pytest.mark.asyncio

TWO_ERRORS = 2


def _make_payment(amount_value: str | None) -> Payment:
    amount = (
        Amount(value=Decimal(amount_value), transcription=None)
        if amount_value is not None
        else None
    )
    return Payment(
        amount=amount,
        vat=Vat(amount=None, rate=None),
        include_vat=False,
    )


def _make_total_amount_field(
    *,
    total_amount: str | None,
    taxes_amounts: list[str | None] | None,
) -> TotalAmountField:
    taxes = [_make_payment(value) for value in taxes_amounts or []]
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
        AdvancePaymentsField(value=advances, sources=[])
        if advances is not None
        else None
    )
    return await check.execute()


async def test_total_amounts_succeeds_when_total_taxes_and_advances_match() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=["100.00"],
        advances=[
            AdvancePayment(
                percent=Decimal("50.00"),
                total=_make_payment("50.00"),
                payments=[_make_payment("50.00")],
            ),
            AdvancePayment(
                percent=Decimal("50.00"),
                total=_make_payment("50.00"),
                payments=[_make_payment("50.00")],
            ),
        ],
    )

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_total_amounts_fails_when_total_and_taxes_differ() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=["90.00"],
        advances=None,
    )

    assert result.status == CheckStatus.FAILED
    assert any(isinstance(err, AmountDiscrepancyError) for err in result.errors)


async def test_total_amounts_fails_when_advance_total_and_payments_differ() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=["100.00"],
        advances=[
            AdvancePayment(
                percent=Decimal("100.00"),
                total=_make_payment("100.00"),
                payments=[_make_payment("90.00")],
            ),
        ],
    )

    assert result.status == CheckStatus.FAILED
    assert any(isinstance(err, AmountDiscrepancyError) for err in result.errors)


async def test_total_amounts_skips_none_amounts_without_crash() -> None:
    with pytest.raises(InsufficientCheckDataError):
        await _run_check(
            total_amount=None,
            taxes_amounts=[None],
            advances=[
                AdvancePayment(
                    percent=None,
                    total=None,
                    payments=[],
                )
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
    assert any(isinstance(err, AmountDiscrepancyError) for err in result.errors)


async def test_total_amounts_succeeds_with_only_total_amount() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=None,
        advances=None,
    )

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


async def test_total_amounts_succeeds_with_multiple_advances_and_nested_payments() -> (
    None
):
    result = await _run_check(
        total_amount="300.00",
        taxes_amounts=["300.00"],
        advances=[
            AdvancePayment(
                percent=Decimal("50.00"),
                total=_make_payment("150.00"),
                payments=[_make_payment("100.00"), _make_payment("50.00")],
            ),
            AdvancePayment(
                percent=Decimal("50.00"),
                total=_make_payment("150.00"),
                payments=[_make_payment("120.00"), _make_payment("30.00")],
            ),
        ],
    )

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


# --- аванс только с total, без payments ---


async def test_advance_with_only_total_matches_contract_success() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=None,
        advances=[
            AdvancePayment(percent=None, total=_make_payment("100.00"), payments=[]),
        ],
    )
    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_advance_with_only_total_differs_from_contract_fails() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=None,
        advances=[
            AdvancePayment(percent=None, total=_make_payment("90.00"), payments=[]),
        ],
    )
    assert result.status == CheckStatus.FAILED
    assert any(isinstance(err, AmountDiscrepancyError) for err in result.errors)


# --- аванс только с payments, без total ---


async def test_advance_with_only_payments_matches_contract_success() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=None,
        advances=[
            AdvancePayment(
                percent=None,
                total=None,
                payments=[_make_payment("60.00"), _make_payment("40.00")],
            ),
        ],
    )
    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_advance_with_only_payments_differs_from_contract_fails() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=None,
        advances=[
            AdvancePayment(
                percent=None,
                total=None,
                payments=[_make_payment("90.00")],
            ),
        ],
    )
    assert result.status == CheckStatus.FAILED
    assert any(isinstance(err, AmountDiscrepancyError) for err in result.errors)


# --- смешанные авансы: одни с total, другие с payments ---


async def test_mixed_advances_total_only_and_payments_only_success() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=None,
        advances=[
            AdvancePayment(percent=None, total=_make_payment("60.00"), payments=[]),
            AdvancePayment(
                percent=None,
                total=None,
                payments=[_make_payment("40.00")],
            ),
        ],
    )
    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


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
            AdvancePayment(percent=None, total=_make_payment("80.00"), payments=[]),
        ],
    )
    assert result.status == CheckStatus.FAILED
    assert len(result.errors) == TWO_ERRORS
    assert all(isinstance(err, AmountDiscrepancyError) for err in result.errors)


async def test_within_advance_and_cross_source_errors_both_collected() -> None:
    result = await _run_check(
        total_amount="100.00",
        taxes_amounts=None,
        advances=[
            AdvancePayment(
                percent=None,
                total=_make_payment("80.00"),
                payments=[_make_payment("70.00")],
            ),
        ],
    )
    assert result.status == CheckStatus.FAILED
    assert len(result.errors) == TWO_ERRORS
    assert all(isinstance(err, AmountDiscrepancyError) for err in result.errors)


def _make_vat_payment(
    value: str,
    *,
    rate: str | None = None,
    vat_amount: str | None = None,
    include_vat: bool,
) -> Payment:
    return Payment(
        amount=Amount(value=Decimal(value), transcription=None),
        vat=Vat(
            amount=(
                Amount(value=Decimal(vat_amount), transcription=None)
                if vat_amount is not None
                else None
            ),
            rate=Decimal(rate) if rate is not None else None,
        ),
        include_vat=include_vat,
    )


async def test_total_amounts_succeeds_when_total_gross_and_tax_net_match() -> None:
    check = CheckTotalAmountsValidation(tolerance=AMOUNT_TOLERANCE)
    check.total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_vat_payment("120.00", rate="20.00", include_vat=True),
            taxes=[_make_vat_payment("100.00", rate="20.00", include_vat=False)],
        ),
        sources=[],
    )
    check.advance_payments_field = None

    result = await check.execute()

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_total_amounts_uses_vat_amount_when_rate_is_missing() -> None:
    check = CheckTotalAmountsValidation(tolerance=AMOUNT_TOLERANCE)
    check.total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_vat_payment("120.00", vat_amount="20.00", include_vat=True),
            taxes=[_make_vat_payment("100.00", vat_amount="20.00", include_vat=False)],
        ),
        sources=[],
    )
    check.advance_payments_field = None

    result = await check.execute()

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_total_amounts_falls_back_to_raw_when_tax_lacks_rate() -> None:
    check = CheckTotalAmountsValidation(tolerance=AMOUNT_TOLERANCE)
    check.total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_vat_payment("100.00", rate="20.00", include_vat=False),
            taxes=[_make_payment("100.00")],
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
            total=_make_vat_payment("120.00", rate="20.00", include_vat=True),
            taxes=[_make_vat_payment("120.00", rate="20.00", include_vat=False)],
        ),
        sources=[],
    )
    check.advance_payments_field = None

    result = await check.execute()

    assert result.status == CheckStatus.FAILED
    assert any(isinstance(err, AmountDiscrepancyError) for err in result.errors)


async def test_total_amounts_uses_excluding_vat_when_gross_unavailable() -> None:
    check = CheckTotalAmountsValidation(tolerance=AMOUNT_TOLERANCE)
    check.total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=_make_vat_payment("120.00", rate="20.00", include_vat=True),
            taxes=[
                Payment(
                    amount=Amount(value=Decimal("100.00"), transcription=None),
                    vat=Vat(amount=None, rate=None),
                    include_vat=False,
                )
            ],
        ),
        sources=[],
    )
    check.advance_payments_field = None

    result = await check.execute()

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []
