from decimal import Decimal

import pytest

from app.domain.checks.check_tax_rates_validation import CheckTaxRatesValidation
from app.domain.checks.errors import InsufficientCheckDataError
from app.domain.entities import (
    AdvancePayment,
    AdvancePaymentsField,
    Money,
    Payment,
    PaymentList,
    TotalAmount,
    TotalAmountField,
    Vat,
)
from app.domain.entities.errors import PaymentVatRatesDifferError
from app.domain.entities.validation import CheckStatus


pytestmark = pytest.mark.asyncio
TWO_ERRORS = 2


def _payment(*, vat_rate: Decimal | None) -> Payment:
    return Payment(
        amount=Money(value=Decimal("100.00"), transcription=None),
        vat=Vat(amount=None, rate=vat_rate),
        include_vat=False,
    )


def _total_amount_field(
    *,
    total_rate: Decimal | None,
    tax_rates: list[Decimal | None] | None,
) -> TotalAmountField:
    taxes = PaymentList([_payment(vat_rate=r) for r in tax_rates or []])
    return TotalAmountField(
        value=TotalAmount(
            total=_payment(vat_rate=total_rate),
            taxes=taxes,
        ),
        sources=[],
    )


def _advance(
    *,
    total_rate: Decimal | None,
    payments: list[Payment] | None = None,
) -> AdvancePayment:
    return AdvancePayment(
        percent=None,
        total=_payment(vat_rate=total_rate) if total_rate is not None else None,
        payments=payments or [],
    )


async def _run(
    *,
    total_rate: Decimal | None,
    tax_rates: list[Decimal | None] | None,
    advances: list[AdvancePayment] | None,
):
    check = CheckTaxRatesValidation()
    check.total_amount_field = _total_amount_field(
        total_rate=total_rate,
        tax_rates=tax_rates,
    )
    check.advance_payments_field = (
        AdvancePaymentsField(value=advances, sources=[])
        if advances is not None
        else None
    )
    return await check.execute()


async def test_no_advances_no_taxes_success() -> None:
    r = await _run(total_rate=Decimal(20), tax_rates=None, advances=None)
    assert r.status == CheckStatus.SUCCESS
    assert r.errors == []


async def test_no_advances_no_taxes_empty_list_success() -> None:
    r = await _run(total_rate=Decimal(20), tax_rates=[], advances=[])
    assert r.status == CheckStatus.SUCCESS
    assert r.errors == []


async def test_no_advances_one_tax_line_both_rates_none_skips() -> None:
    check = CheckTaxRatesValidation()
    check.total_amount_field = _total_amount_field(total_rate=None, tax_rates=[None])
    check.advance_payments_field = None
    with pytest.raises(InsufficientCheckDataError):
        await check.execute()


async def test_no_rate_in_total_or_taxes_but_advance_has_rate_tax_line_fails() -> None:
    r = await _run(
        total_rate=None,
        tax_rates=[None],
        advances=[
            AdvancePayment(
                percent=None,
                total=None,
                payments=[_payment(vat_rate=Decimal(20))],
            ),
        ],
    )
    assert r.status == CheckStatus.SUCCESS


async def test_no_rate_in_total_no_tax_lines_but_advance_has_rate_success() -> None:
    r = await _run(
        total_rate=None,
        tax_rates=[],
        advances=[
            AdvancePayment(
                percent=None,
                total=None,
                payments=[_payment(vat_rate=Decimal(20))],
            ),
        ],
    )
    assert r.status == CheckStatus.SUCCESS
    assert r.errors == []


async def test_no_advances_one_tax_line_rates_match_success() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=[Decimal(20)],
        advances=None,
    )
    assert r.status == CheckStatus.SUCCESS


async def test_no_advances_one_tax_line_rates_differ_failed() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=[Decimal(10)],
        advances=None,
    )
    assert r.status == CheckStatus.FAILED
    err = r.errors[0]
    assert isinstance(err, PaymentVatRatesDifferError)
    assert err.rate_one == Decimal(20)
    assert err.rate_two == Decimal(10)


async def test_no_advances_multiple_taxes_line_differs_from_total_failed() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=[Decimal(20), Decimal(10)],
        advances=None,
    )
    assert r.status == CheckStatus.FAILED
    err = r.errors[0]
    assert isinstance(err, PaymentVatRatesDifferError)
    assert err.rate_one == Decimal(20)
    assert err.rate_two == Decimal(10)


async def test_no_advances_multiple_taxes_all_lines_match_total_success() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=[Decimal(20), Decimal(20)],
        advances=None,
    )
    assert r.status == CheckStatus.SUCCESS


async def test_no_advances_multiple_taxes_no_total_rate_all_none_not_found() -> None:
    with pytest.raises(InsufficientCheckDataError):
        await _run(
            total_rate=None,
            tax_rates=[None, None],
            advances=None,
        )


async def test_no_advances_multiple_taxes_no_total_but_lines_have_rates_success() -> (
    None
):
    r = await _run(
        total_rate=None,
        tax_rates=[Decimal(20), Decimal(10)],
        advances=None,
    )
    assert r.status == CheckStatus.SUCCESS


async def test_advances_with_payments_match_advance_total() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=None,
        advances=[
            _advance(
                total_rate=Decimal(20),
                payments=[_payment(vat_rate=Decimal(20))],
            ),
        ],
    )
    assert r.status == CheckStatus.SUCCESS


async def test_advances_with_payments_no_advance_total_skips_line_check() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=None,
        advances=[
            AdvancePayment(
                percent=None,
                total=None,
                payments=[
                    _payment(vat_rate=Decimal(20)),
                    _payment(vat_rate=Decimal(20)),
                ],
            ),
        ],
    )
    assert r.status == CheckStatus.SUCCESS


async def test_advances_with_payments_line_differs_from_advance_total_failed() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=None,
        advances=[
            _advance(
                total_rate=Decimal(20),
                payments=[
                    _payment(vat_rate=Decimal(20)),
                    _payment(vat_rate=Decimal(10)),
                ],
            ),
        ],
    )
    assert r.status == CheckStatus.FAILED
    err = r.errors[0]
    assert isinstance(err, PaymentVatRatesDifferError)
    assert err.rate_one == Decimal(20)
    assert err.rate_two == Decimal(10)


async def test_advances_with_payments_no_advance_total_mixed_rates_success() -> None:
    r = await _run(
        total_rate=None,
        tax_rates=None,
        advances=[
            AdvancePayment(
                percent=None,
                total=None,
                payments=[
                    _payment(vat_rate=Decimal(20)),
                    _payment(vat_rate=Decimal(10)),
                ],
            ),
        ],
    )
    assert r.status == CheckStatus.SUCCESS


async def test_advances_with_payments_no_advance_total_all_rates_none_not_found() -> (
    None
):
    with pytest.raises(InsufficientCheckDataError):
        await _run(
            total_rate=None,
            tax_rates=None,
            advances=[
                AdvancePayment(
                    percent=None,
                    total=None,
                    payments=[
                        _payment(vat_rate=None),
                        _payment(vat_rate=None),
                    ],
                ),
            ],
        )


async def test_advances_with_taxes_and_flat_advances_success() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=[Decimal(20)],
        advances=[_advance(total_rate=Decimal(20))],
    )
    assert r.status == CheckStatus.SUCCESS


async def test_flat_advances_match_contract_success() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=None,
        advances=[
            _advance(total_rate=Decimal(20)),
            _advance(total_rate=Decimal(20)),
        ],
    )
    assert r.status == CheckStatus.SUCCESS


async def test_flat_advances_differ_from_contract_failed() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=None,
        advances=[
            _advance(total_rate=Decimal(20)),
            _advance(total_rate=Decimal(10)),
        ],
    )
    assert r.status == CheckStatus.FAILED
    err = r.errors[0]
    assert isinstance(err, PaymentVatRatesDifferError)
    assert err.rate_one == Decimal(20)
    assert err.rate_two == Decimal(10)


async def test_flat_advances_no_contract_rate_differ_success() -> None:
    r = await _run(
        total_rate=None,
        tax_rates=[],
        advances=[
            _advance(total_rate=Decimal(20)),
            _advance(total_rate=Decimal(10)),
        ],
    )
    assert r.status == CheckStatus.SUCCESS
    assert r.errors == []


async def test_flat_advances_skip_none_total_success() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=None,
        advances=[
            AdvancePayment(percent=None, total=None, payments=[]),
            _advance(total_rate=Decimal(20)),
        ],
    )
    assert r.status == CheckStatus.SUCCESS


async def test_flat_advance_total_amount_without_vat_rate_success() -> None:
    r = await _run(
        total_rate=Decimal(22),
        tax_rates=[],
        advances=[
            AdvancePayment(
                percent=Decimal(50),
                total=_payment(vat_rate=None),
                payments=[],
            ),
        ],
    )
    assert r.status == CheckStatus.SUCCESS
    assert r.errors == []


# --- execute: taxes со смешанными None/valid ставками ---


async def test_taxes_with_none_rate_among_valid_collects_not_found() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=[Decimal(20), None],
        advances=None,
    )
    assert r.status == CheckStatus.SUCCESS


# --- Branch A: нет payments, tax_rates не пустой ---


async def test_flat_advance_rate_in_tax_rates_success() -> None:
    r = await _run(
        total_rate=None,
        tax_rates=[Decimal(20), Decimal(10)],
        advances=[_advance(total_rate=Decimal(20))],
    )
    assert r.status == CheckStatus.SUCCESS


async def test_flat_advance_rate_not_in_tax_rates_failed() -> None:
    r = await _run(
        total_rate=None,
        tax_rates=[Decimal(20), Decimal(10)],
        advances=[_advance(total_rate=Decimal(5))],
    )
    assert r.status == CheckStatus.FAILED
    err = r.errors[0]
    assert isinstance(err, PaymentVatRatesDifferError)
    assert err.index == 0
    assert err.rate_one == Decimal(5)
    assert err.rate_two is None


# --- Branch B: есть payments, нет aggregate rate ---


async def test_advance_payments_no_total_mismatch_contract_rate_failed() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=None,
        advances=[
            AdvancePayment(
                percent=None,
                total=None,
                payments=[
                    _payment(vat_rate=Decimal(20)),
                    _payment(vat_rate=Decimal(10)),
                ],
            ),
        ],
    )
    assert r.status == CheckStatus.FAILED
    err = r.errors[0]
    assert isinstance(err, PaymentVatRatesDifferError)
    assert err.rate_one == Decimal(20)
    assert err.rate_two == Decimal(10)


async def test_advance_payments_no_total_all_rates_in_tax_rates_success() -> None:
    r = await _run(
        total_rate=None,
        tax_rates=[Decimal(20), Decimal(10)],
        advances=[
            AdvancePayment(
                percent=None,
                total=None,
                payments=[
                    _payment(vat_rate=Decimal(20)),
                    _payment(vat_rate=Decimal(10)),
                ],
            ),
        ],
    )
    assert r.status == CheckStatus.SUCCESS


async def test_advance_payments_no_total_rate_not_in_tax_rates_failed() -> None:
    r = await _run(
        total_rate=None,
        tax_rates=[Decimal(20)],
        advances=[
            AdvancePayment(
                percent=None,
                total=None,
                payments=[
                    _payment(vat_rate=Decimal(20)),
                    _payment(vat_rate=Decimal(10)),
                ],
            ),
        ],
    )
    assert r.status == CheckStatus.FAILED
    err = r.errors[0]
    assert isinstance(err, PaymentVatRatesDifferError)
    assert err.index == 0
    assert err.rate_one == Decimal(10)
    assert err.rate_two is None


async def test_advance_payments_no_total_mixed_none_valid_collects_not_found() -> None:
    r = await _run(
        total_rate=None,
        tax_rates=None,
        advances=[
            AdvancePayment(
                percent=None,
                total=None,
                payments=[_payment(vat_rate=None), _payment(vat_rate=Decimal(20))],
            ),
        ],
    )
    assert r.status == CheckStatus.SUCCESS


# --- Branch C: есть payments И aggregate rate ---


async def test_advance_total_differs_payments_match_aggregate_failed() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=None,
        advances=[
            _advance(
                total_rate=Decimal(10),
                payments=[_payment(vat_rate=Decimal(10))],
            ),
        ],
    )
    assert r.status == CheckStatus.FAILED
    err = r.errors[0]
    assert isinstance(err, PaymentVatRatesDifferError)
    assert err.index == 0
    assert err.rate_one == Decimal(20)
    assert err.rate_two == Decimal(10)


async def test_advance_total_in_tax_rates_payments_match_aggregate_success() -> None:
    r = await _run(
        total_rate=None,
        tax_rates=[Decimal(20), Decimal(10)],
        advances=[
            _advance(
                total_rate=Decimal(20),
                payments=[_payment(vat_rate=Decimal(20))],
            ),
        ],
    )
    assert r.status == CheckStatus.SUCCESS


async def test_advance_total_in_tax_rates_payment_differs_from_aggregate_failed() -> (
    None
):
    r = await _run(
        total_rate=None,
        tax_rates=[Decimal(20), Decimal(10)],
        advances=[
            _advance(
                total_rate=Decimal(20),
                payments=[_payment(vat_rate=Decimal(10))],
            ),
        ],
    )
    assert r.status == CheckStatus.FAILED
    err = r.errors[0]
    assert isinstance(err, PaymentVatRatesDifferError)
    assert err.rate_one == Decimal(20)
    assert err.rate_two == Decimal(10)


# --- Сбор всех ошибок по нескольким авансам ---


async def test_multiple_advances_collects_errors_for_all() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=None,
        advances=[
            _advance(total_rate=Decimal(10)),
            _advance(total_rate=Decimal(5)),
        ],
    )
    assert r.status == CheckStatus.FAILED
    assert len(r.errors) == TWO_ERRORS
    indices = {
        err.index for err in r.errors if isinstance(err, PaymentVatRatesDifferError)
    }
    assert indices == {0, 1}
