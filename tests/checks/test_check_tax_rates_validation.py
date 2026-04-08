from decimal import Decimal

import pytest

from app.domain.checks.check_tax_rates_validation import CheckTaxRatesValidation
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
from app.domain.entities.validation_errors import (
    PaymentVatRateNotFoundCheckResult,
    PaymentVatRatesDifferCheckResult,
)


pytestmark = pytest.mark.asyncio


def _payment(*, vat_rate: Decimal | None) -> Payment:
    return Payment(
        amount=Amount(value=Decimal("100.00"), transcription=None),
        vat=Vat(amount=None, rate=vat_rate),
        include_vat=False,
    )


def _total_amount_field(
    *,
    total_rate: Decimal | None,
    tax_rates: list[Decimal | None] | None,
) -> TotalAmountField:
    taxes = None
    if tax_rates is not None:
        taxes = [_payment(vat_rate=r) for r in tax_rates]
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
        payments=payments,
    )


async def _run(
    *,
    total_rate: Decimal | None,
    tax_rates: list[Decimal | None] | None,
    advances: list[AdvancePayment] | None,
):
    check = CheckTaxRatesValidation()
    ta = _total_amount_field(total_rate=total_rate, tax_rates=tax_rates)
    adv_field = (
        AdvancePaymentsField(value=advances, sources=[])
        if advances is not None
        else None
    )
    return await check.execute(ta, adv_field)


async def test_no_advances_no_taxes_success() -> None:
    r = await _run(total_rate=Decimal(20), tax_rates=None, advances=None)
    assert r.status == CheckStatus.success
    assert r.errors == []


async def test_no_advances_no_taxes_empty_list_success() -> None:
    r = await _run(total_rate=Decimal(20), tax_rates=[], advances=[])
    assert r.status == CheckStatus.success
    assert r.errors == []


async def test_no_advances_one_tax_line_both_rates_none_not_found() -> None:
    r = await _run(total_rate=None, tax_rates=[None], advances=None)
    assert r.status == CheckStatus.failed
    assert len(r.errors) == 1
    assert isinstance(r.errors[0], PaymentVatRateNotFoundCheckResult)


async def test_no_rate_in_total_or_taxes_but_advance_has_rate_success() -> None:
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
    assert r.status == CheckStatus.success
    assert r.errors == []


async def test_no_advances_one_tax_line_rates_match_success() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=[Decimal(20)],
        advances=None,
    )
    assert r.status == CheckStatus.success


async def test_no_advances_one_tax_line_rates_differ_failed() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=[Decimal(10)],
        advances=None,
    )
    assert r.status == CheckStatus.failed
    err = r.errors[0]
    assert isinstance(err, PaymentVatRatesDifferCheckResult)
    assert err.rate_one == Decimal(20)
    assert err.rate_two == Decimal(10)


async def test_no_advances_multiple_taxes_line_differs_from_total_failed() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=[Decimal(20), Decimal(10)],
        advances=None,
    )
    assert r.status == CheckStatus.failed
    err = r.errors[0]
    assert isinstance(err, PaymentVatRatesDifferCheckResult)
    assert err.rate_one == Decimal(20)
    assert err.rate_two == Decimal(10)


async def test_no_advances_multiple_taxes_all_lines_match_total_success() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=[Decimal(20), Decimal(20)],
        advances=None,
    )
    assert r.status == CheckStatus.success


async def test_no_advances_multiple_taxes_no_total_rate_all_none_not_found() -> None:
    r = await _run(
        total_rate=None,
        tax_rates=[None, None],
        advances=None,
    )
    assert r.status == CheckStatus.failed
    assert isinstance(r.errors[0], PaymentVatRateNotFoundCheckResult)


async def test_no_advances_multiple_taxes_no_total_but_lines_have_rates_success() -> None:
    r = await _run(
        total_rate=None,
        tax_rates=[Decimal(20), Decimal(10)],
        advances=None,
    )
    assert r.status == CheckStatus.success


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
    assert r.status == CheckStatus.success


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
    assert r.status == CheckStatus.success


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
    assert r.status == CheckStatus.failed
    err = r.errors[0]
    assert isinstance(err, PaymentVatRatesDifferCheckResult)
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
    assert r.status == CheckStatus.success


async def test_advances_with_payments_no_advance_total_all_rates_none_not_found() -> None:
    r = await _run(
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
    assert r.status == CheckStatus.failed
    assert isinstance(r.errors[0], PaymentVatRateNotFoundCheckResult)


async def test_advances_with_taxes_and_flat_advances_success() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=[Decimal(20)],
        advances=[_advance(total_rate=Decimal(20))],
    )
    assert r.status == CheckStatus.success


async def test_flat_advances_match_contract_success() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=None,
        advances=[
            _advance(total_rate=Decimal(20)),
            _advance(total_rate=Decimal(20)),
        ],
    )
    assert r.status == CheckStatus.success


async def test_flat_advances_differ_from_contract_failed() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=None,
        advances=[
            _advance(total_rate=Decimal(20)),
            _advance(total_rate=Decimal(10)),
        ],
    )
    assert r.status == CheckStatus.failed
    err = r.errors[0]
    assert isinstance(err, PaymentVatRatesDifferCheckResult)
    assert err.rate_one == Decimal(20)
    assert err.rate_two == Decimal(10)


async def test_flat_advances_skip_none_total_success() -> None:
    r = await _run(
        total_rate=Decimal(20),
        tax_rates=None,
        advances=[
            AdvancePayment(percent=None, total=None, payments=None),
            _advance(total_rate=Decimal(20)),
        ],
    )
    assert r.status == CheckStatus.success
