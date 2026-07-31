from decimal import Decimal

from app.domain.checks.check_amounts_validation import CheckTotalAmountsValidation
from app.domain.checks.check_values_validation import CheckValuesValidation
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
from app.domain.entities.errors import (
    AmountNotPositiveError,
    VatAmountDiscrepancyError,
    VatAmountNotPositiveError,
    VatRateNotPositiveError,
)
from app.domain.entities.validation import CheckExecutionResult, CheckStatus


def _pay(
    *,
    amount: str | None = "100.00",
    vat_amount: str | None = "20.00",
    vat_rate: str | None = "20.00",
    include_vat: VatInclusion = VatInclusion.INCLUDED,
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


def _advance(
    *, percent: Decimal | None, total: Payment | None, payments: PaymentList
) -> AdvancePayment:
    base = total if total is not None else EMPTY_PAYMENT
    return AdvancePayment(
        percent=percent,
        amount=base.amount,
        vat=base.vat,
        include_vat=base.include_vat,
        payments=payments,
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
    total_amount_field = _make_total_amount_field(total=total, taxes=taxes or [])
    advance_payments_field = (
        AdvancePaymentsField(value=AdvancePaymentList(advances), sources=[])
        if advances is not None
        else None
    )
    fields = [total_amount_field]
    if advance_payments_field is not None:
        fields.append(advance_payments_field)

    values_check = CheckValuesValidation()
    values_check.prepare(fields)
    values_result = await values_check.execute()

    amounts_check = CheckTotalAmountsValidation(tolerance=tolerance)
    amounts_check.prepare(fields)
    amounts_result = await amounts_check.execute()

    errors = [*values_result.errors, *amounts_result.errors]
    return CheckExecutionResult(
        label="VatConsistencyRegression",
        status=CheckStatus.FAILED if errors else CheckStatus.SUCCESS,
        errors=errors,
    )


async def test_vat_consistency_succeeds_when_sums_are_valid() -> None:
    r = await _run(
        total=_pay(amount="120.00", vat_amount="20.00"),
        taxes=[_pay(amount="120.00", vat_amount="20.00")],
        advances=[
            _advance(
                percent=Decimal("50.00"),
                total=_pay(amount="60.00", vat_amount="10.00"),
                payments=PaymentList([_pay(amount="60.00", vat_amount="10.00")]),
            ),
            _advance(
                percent=Decimal("50.00"),
                total=_pay(amount="60.00", vat_amount="10.00"),
                payments=PaymentList([_pay(amount="60.00", vat_amount="10.00")]),
            ),
        ],
    )
    assert r.status == CheckStatus.SUCCESS
    assert r.errors == []


async def test_vat_consistency_fails_when_total_and_taxes_sums_differ() -> None:
    r = await _run(
        total=_pay(amount="120.00", vat_amount="20.00"),
        taxes=[_pay(amount="60.00", vat_amount="10.00")],
    )
    assert r.status == CheckStatus.FAILED
    assert any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)


async def test_vat_consistency_compares_sums_when_amount_missing() -> None:
    r = await _run(
        total=_pay(amount="120.00", vat_amount="20.00"),
        taxes=[_pay(amount="120.00", vat_amount="20.00")],
        advances=[
            _advance(
                percent=Decimal("100.00"),
                total=_pay(amount=None, vat_amount="20.00"),
                payments=PaymentList([_pay(amount=None, vat_amount="20.00")]),
            ),
        ],
    )
    assert r.status == CheckStatus.SUCCESS
    assert r.errors == []


async def test_vat_consistency_fails_when_amount_not_positive() -> None:
    r = await _run(total=_pay(amount="0.00", vat_amount="20.00"))
    assert r.status == CheckStatus.FAILED
    assert any(isinstance(e, AmountNotPositiveError) for e in r.errors)


async def test_vat_consistency_allows_zero_vat_amount() -> None:
    r = await _run(total=_pay(amount=None, vat_amount="0.00"))
    assert r.status == CheckStatus.SUCCESS
    assert r.errors == []


async def test_vat_consistency_ignores_empty_taxes_list() -> None:
    r = await _run(total=_pay(amount="120.00", vat_amount="20.00"), taxes=[])
    assert r.status == CheckStatus.SUCCESS
    assert not any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)


async def test_vat_consistency_ignores_advances_without_totals_and_payments() -> None:
    r = await _run(
        total=_pay(amount="120.00", vat_amount="20.00"),
        advances=[
            _advance(percent=Decimal("50.00"), total=None, payments=PaymentList([])),
            _advance(percent=Decimal("50.00"), total=None, payments=PaymentList([])),
        ],
    )
    assert r.status == CheckStatus.SUCCESS
    assert not any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)


async def test_vat_consistency_negative_vat_amount_fails() -> None:
    r = await _run(total=_pay(vat_amount="-5.00"))
    assert r.status == CheckStatus.FAILED
    assert any(isinstance(e, VatAmountNotPositiveError) for e in r.errors)


async def test_vat_consistency_negative_vat_rate_fails() -> None:
    r = await _run(total=_pay(vat_rate="-20.00"))
    assert r.status == CheckStatus.FAILED
    assert any(isinstance(e, VatRateNotPositiveError) for e in r.errors)


async def test_vat_consistency_negative_vat_excluded_from_sum() -> None:
    r = await _run(
        total=_pay(amount=None, vat_amount="20.00"),
        taxes=[_pay(amount=None, vat_amount="-5.00")],
    )
    assert r.status == CheckStatus.FAILED
    assert any(isinstance(e, VatAmountNotPositiveError) for e in r.errors)
    assert any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)


async def test_vat_consistency_advance_aggregate_vs_payments_discrepancy() -> None:
    r = await _run(
        total=_pay(amount=None, vat_amount="20.00"),
        advances=[
            _advance(
                percent=None,
                total=_pay(amount=None, vat_amount="20.00"),
                payments=PaymentList(
                    [
                        _pay(amount=None, vat_amount="12.00"),
                        _pay(amount=None, vat_amount="3.00"),
                    ]
                ),
            ),
        ],
    )
    assert r.status == CheckStatus.FAILED
    assert any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)


async def test_vat_consistency_advance_without_total_matches() -> None:
    r = await _run(
        total=_pay(amount=None, vat_amount="20.00"),
        advances=[
            _advance(
                percent=None,
                total=None,
                payments=PaymentList(
                    [
                        _pay(amount=None, vat_amount="12.00"),
                        _pay(amount=None, vat_amount="8.00"),
                    ]
                ),
            ),
        ],
    )
    assert r.status == CheckStatus.SUCCESS
    assert r.errors == []


async def test_vat_consistency_advance_without_total_differs_fails() -> None:
    r = await _run(
        total=_pay(amount=None, vat_amount="20.00"),
        advances=[
            _advance(
                percent=None,
                total=None,
                payments=PaymentList(
                    [
                        _pay(amount=None, vat_amount="12.00"),
                        _pay(amount=None, vat_amount="3.00"),
                    ]
                ),
            ),
        ],
    )
    assert r.status == CheckStatus.FAILED
    assert any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)


async def test_vat_consistency_multiple_advance_totals_summed() -> None:
    r = await _run(
        total=_pay(amount=None, vat_amount="20.00"),
        advances=[
            _advance(
                percent=None,
                total=_pay(amount=None, vat_amount="12.00"),
                payments=PaymentList([]),
            ),
            _advance(
                percent=None,
                total=_pay(amount=None, vat_amount="8.00"),
                payments=PaymentList([]),
            ),
        ],
    )
    assert r.status == CheckStatus.SUCCESS
    assert r.errors == []


async def test_vat_consistency_advance_total_differs_from_contract_fails() -> None:
    r = await _run(
        total=_pay(amount=None, vat_amount="20.00"),
        advances=[
            _advance(
                percent=None,
                total=_pay(amount=None, vat_amount="10.00"),
                payments=PaymentList([]),
            ),
        ],
    )
    assert r.status == CheckStatus.FAILED
    assert any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)
