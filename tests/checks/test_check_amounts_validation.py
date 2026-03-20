import asyncio
from decimal import Decimal

from app.domain.entities.single_supplier import (
    AdvancePayment,
    AdvancePaymentsField,
    Amount,
    Payment,
    TotalAmount,
    TotalAmountField,
    Vat,
)
from app.domain.entities.validation import CheckStatus
from app.domain.entities.validation_errors import AmountDiscrepancyCheckResult
from app.domain.service.checks.check_amounts_validation import CheckTotalAmountsValidation


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
    taxes = None
    if taxes_amounts is not None:
        taxes = [_make_payment(value) for value in taxes_amounts]
    return TotalAmountField(
        value=TotalAmount(
            total=_make_payment(total_amount),
            taxes=taxes,
        ),
        sources=[],
    )


def _run_check(
    *,
    total_amount: str | None,
    taxes_amounts: list[str | None] | None,
    advances: list[AdvancePayment] | None,
):
    check = CheckTotalAmountsValidation()
    return asyncio.run(
        check.execute(
            total_amount_field=_make_total_amount_field(
                total_amount=total_amount,
                taxes_amounts=taxes_amounts,
            ),
            advance_payments_field=(
                AdvancePaymentsField(value=advances, sources=[])
                if advances is not None
                else None
            ),
        )
    )


def test_total_amounts_succeeds_when_total_taxes_and_advances_match():
    result = _run_check(
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

    assert result.status == CheckStatus.success
    assert result.errors == []


def test_total_amounts_fails_when_total_and_taxes_differ():
    result = _run_check(
        total_amount="100.00",
        taxes_amounts=["90.00"],
        advances=None,
    )

    assert result.status == CheckStatus.failed
    assert any(isinstance(err, AmountDiscrepancyCheckResult) for err in result.errors)


def test_total_amounts_fails_when_advance_total_and_payments_differ():
    result = _run_check(
        total_amount="100.00",
        taxes_amounts=["100.00"],
        advances=[
            AdvancePayment(
                percent=Decimal("100.00"),
                total=_make_payment("100.00"),
                payments=[_make_payment("90.00")],
            )
        ],
    )

    assert result.status == CheckStatus.failed
    assert any(isinstance(err, AmountDiscrepancyCheckResult) for err in result.errors)


def test_total_amounts_skips_none_amounts_without_crash():
    result = _run_check(
        total_amount=None,
        taxes_amounts=[None],
        advances=[
            AdvancePayment(
                percent=None,
                total=None,
                payments=None,
            )
        ],
    )

    assert result.status == CheckStatus.success
    assert result.errors == []


def test_total_amounts_tolerance_allows_exactly_one_cent():
    result = _run_check(
        total_amount="100.00",
        taxes_amounts=["100.01"],
        advances=None,
    )

    assert result.status == CheckStatus.success
    assert result.errors == []


def test_total_amounts_fails_when_tolerance_exceeded():
    result = _run_check(
        total_amount="100.00",
        taxes_amounts=["100.02"],
        advances=None,
    )

    assert result.status == CheckStatus.failed
    assert any(isinstance(err, AmountDiscrepancyCheckResult) for err in result.errors)


def test_total_amounts_succeeds_with_only_total_amount():
    result = _run_check(
        total_amount="100.00",
        taxes_amounts=None,
        advances=None,
    )

    assert result.status == CheckStatus.success
    assert result.errors == []


def test_total_amounts_succeeds_when_taxes_list_is_empty():
    result = _run_check(
        total_amount="100.00",
        taxes_amounts=[],
        advances=None,
    )

    assert result.status == CheckStatus.success
    assert result.errors == []


def test_total_amounts_succeeds_with_multiple_taxes_when_sum_matches_total():
    result = _run_check(
        total_amount="100.00",
        taxes_amounts=["60.00", "40.00"],
        advances=None,
    )

    assert result.status == CheckStatus.success
    assert result.errors == []


def test_total_amounts_succeeds_with_multiple_advances_and_nested_payments():
    result = _run_check(
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

    assert result.status == CheckStatus.success
    assert result.errors == []
