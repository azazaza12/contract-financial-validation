from decimal import Decimal

from app.domain.checks.check_vat_consistency import CheckVatConsistency
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
from app.domain.entities.errors import (
    AmountNotPositiveError,
    VatAmountDiscrepancyError,
    VatAmountNotPositiveError,
    VatRateNotPositiveError,
)
from app.domain.entities.validation import CheckStatus
from tests.domain.pipeline.check_services_stub import STUB_CHECK_SERVICES


def _pay(
    *,
    amount: str | None = "100.00",
    vat_amount: str | None = "20.00",
    vat_rate: str | None = "20.00",
    include_vat: bool = True,
) -> Payment:
    return Payment(
        amount=Amount(value=Decimal(amount), transcription=None)
        if amount is not None
        else None,
        vat=Vat(
            amount=Amount(value=Decimal(vat_amount), transcription=None)
            if vat_amount is not None
            else None,
            rate=Decimal(vat_rate) if vat_rate is not None else None,
        ),
        include_vat=include_vat,
    )


def _make_total_amount_field(
    *,
    total: Payment,
    taxes: list[Payment] | None = None,
) -> TotalAmountField:
    return TotalAmountField(
        value=TotalAmount(total=total, taxes=taxes or []),
        sources=[],
    )


async def _run(
    *,
    total: Payment,
    taxes: list[Payment] | None = None,
    advances: list[AdvancePayment] | None = None,
    tolerance: Decimal = AMOUNT_TOLERANCE,
):
    check = CheckVatConsistency(tolerance=tolerance)
    check.total_amount_field = _make_total_amount_field(total=total, taxes=taxes or [])
    check.advance_payments_field = (
        AdvancePaymentsField(value=advances, sources=[])
        if advances is not None
        else None
    )
    return await check.execute(STUB_CHECK_SERVICES)


async def test_vat_consistency_succeeds_when_sums_are_valid() -> None:
    r = await _run(
        total=_pay(amount="120.00", vat_amount="20.00"),
        taxes=[_pay(amount="120.00", vat_amount="20.00")],
        advances=[
            AdvancePayment(
                percent=Decimal("50.00"),
                total=_pay(amount="60.00", vat_amount="10.00"),
                payments=[_pay(amount="60.00", vat_amount="10.00")],
            ),
            AdvancePayment(
                percent=Decimal("50.00"),
                total=_pay(amount="60.00", vat_amount="10.00"),
                payments=[_pay(amount="60.00", vat_amount="10.00")],
            ),
        ],
    )
    assert r.status == CheckStatus.success
    assert r.errors == []


async def test_vat_consistency_fails_when_total_and_taxes_sums_differ() -> None:
    r = await _run(
        total=_pay(amount="120.00", vat_amount="20.00"),
        taxes=[_pay(amount="60.00", vat_amount="10.00")],
    )
    assert r.status == CheckStatus.failed
    assert any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)


async def test_vat_consistency_compares_sums_when_amount_missing() -> None:
    r = await _run(
        total=_pay(amount="120.00", vat_amount="20.00"),
        taxes=[_pay(amount="120.00", vat_amount="20.00")],
        advances=[
            AdvancePayment(
                percent=Decimal("100.00"),
                total=_pay(amount=None, vat_amount="20.00"),
                payments=[_pay(amount=None, vat_amount="20.00")],
            ),
        ],
    )
    assert r.status == CheckStatus.success
    assert r.errors == []


async def test_vat_consistency_fails_when_amount_not_positive() -> None:
    r = await _run(total=_pay(amount="0.00", vat_amount="20.00"))
    assert r.status == CheckStatus.failed
    assert any(isinstance(e, AmountNotPositiveError) for e in r.errors)


async def test_vat_consistency_allows_zero_vat_amount() -> None:
    r = await _run(total=_pay(amount=None, vat_amount="0.00"))
    assert r.status == CheckStatus.success
    assert r.errors == []


async def test_vat_consistency_ignores_empty_taxes_list() -> None:
    r = await _run(total=_pay(amount="120.00", vat_amount="20.00"), taxes=[])
    assert r.status == CheckStatus.success
    assert not any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)


async def test_vat_consistency_ignores_advances_without_totals_and_payments() -> None:
    r = await _run(
        total=_pay(amount="120.00", vat_amount="20.00"),
        advances=[
            AdvancePayment(percent=Decimal("50.00"), total=None, payments=[]),
            AdvancePayment(percent=Decimal("50.00"), total=None, payments=[]),
        ],
    )
    assert r.status == CheckStatus.success
    assert not any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)


async def test_vat_consistency_negative_vat_amount_fails() -> None:
    r = await _run(total=_pay(vat_amount="-5.00"))
    assert r.status == CheckStatus.failed
    assert any(isinstance(e, VatAmountNotPositiveError) for e in r.errors)


async def test_vat_consistency_negative_vat_rate_fails() -> None:
    r = await _run(total=_pay(vat_rate="-20.00"))
    assert r.status == CheckStatus.failed
    assert any(isinstance(e, VatRateNotPositiveError) for e in r.errors)


async def test_vat_consistency_negative_vat_excluded_from_sum() -> None:
    r = await _run(
        total=_pay(amount=None, vat_amount="20.00"),
        taxes=[_pay(amount=None, vat_amount="-5.00")],
    )
    assert r.status == CheckStatus.failed
    assert any(isinstance(e, VatAmountNotPositiveError) for e in r.errors)
    assert not any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)


async def test_vat_consistency_advance_aggregate_vs_payments_discrepancy() -> None:
    r = await _run(
        total=_pay(amount=None, vat_amount="20.00"),
        advances=[
            AdvancePayment(
                percent=None,
                total=_pay(amount=None, vat_amount="20.00"),
                payments=[
                    _pay(amount=None, vat_amount="12.00"),
                    _pay(amount=None, vat_amount="3.00"),
                ],
            ),
        ],
    )
    assert r.status == CheckStatus.failed
    assert any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)


async def test_vat_consistency_advance_without_total_matches() -> None:
    r = await _run(
        total=_pay(amount=None, vat_amount="20.00"),
        advances=[
            AdvancePayment(
                percent=None,
                total=None,
                payments=[
                    _pay(amount=None, vat_amount="12.00"),
                    _pay(amount=None, vat_amount="8.00"),
                ],
            ),
        ],
    )
    assert r.status == CheckStatus.success
    assert r.errors == []


async def test_vat_consistency_advance_without_total_differs_fails() -> None:
    r = await _run(
        total=_pay(amount=None, vat_amount="20.00"),
        advances=[
            AdvancePayment(
                percent=None,
                total=None,
                payments=[
                    _pay(amount=None, vat_amount="12.00"),
                    _pay(amount=None, vat_amount="3.00"),
                ],
            ),
        ],
    )
    assert r.status == CheckStatus.failed
    assert any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)


async def test_vat_consistency_multiple_advance_totals_summed() -> None:
    r = await _run(
        total=_pay(amount=None, vat_amount="20.00"),
        advances=[
            AdvancePayment(
                percent=None, total=_pay(amount=None, vat_amount="12.00"), payments=[]
            ),
            AdvancePayment(
                percent=None, total=_pay(amount=None, vat_amount="8.00"), payments=[]
            ),
        ],
    )
    assert r.status == CheckStatus.success
    assert r.errors == []


async def test_vat_consistency_advance_total_differs_from_contract_fails() -> None:
    r = await _run(
        total=_pay(amount=None, vat_amount="20.00"),
        advances=[
            AdvancePayment(
                percent=None, total=_pay(amount=None, vat_amount="10.00"), payments=[]
            ),
        ],
    )
    assert r.status == CheckStatus.failed
    assert any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)
