from decimal import Decimal

from app.domain.checks.check_taxes_validation import CheckTaxesValidation
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
    VatAmountCalculationDiscrepancyError,
    VatAmountDiscrepancyError,
    VatAmountNotPositiveError,
    VatRateNotPositiveError,
)
from app.domain.entities.validation import CheckStatus
from tests.domain.pipeline.check_services_stub import STUB_CHECK_SERVICES


def _make_payment(
    *,
    amount: str | None,
    vat_amount: str,
    vat_rate: str,
    include_vat: bool,
) -> Payment:
    amount_obj = (
        Amount(value=Decimal(amount), transcription=None)
        if amount is not None
        else None
    )
    return Payment(
        amount=amount_obj,
        vat=Vat(
            amount=Amount(value=Decimal(vat_amount), transcription=None),
            rate=Decimal(vat_rate),
        ),
        include_vat=include_vat,
    )


def _make_total_amount_field(
    *,
    total: Payment,
    taxes: list[Payment] | None,
) -> TotalAmountField:
    return TotalAmountField(
        value=TotalAmount(total=total, taxes=taxes or []),
        sources=[],
    )


async def test_check_nds_succeeds_when_formula_and_sums_are_valid() -> None:
    check = CheckTaxesValidation(tolerance=AMOUNT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="20.00",
        vat_rate="20.00",
        include_vat=True,
    )
    taxes = [
        _make_payment(
            amount="120.00",
            vat_amount="20.00",
            vat_rate="20.00",
            include_vat=True,
        ),
    ]
    advances = [
        AdvancePayment(
            percent=Decimal("50.00"),
            total=_make_payment(
                amount="60.00",
                vat_amount="10.00",
                vat_rate="20.00",
                include_vat=True,
            ),
            payments=[
                _make_payment(
                    amount="60.00",
                    vat_amount="10.00",
                    vat_rate="20.00",
                    include_vat=True,
                ),
            ],
        ),
        AdvancePayment(
            percent=Decimal("50.00"),
            total=_make_payment(
                amount="60.00",
                vat_amount="10.00",
                vat_rate="20.00",
                include_vat=True,
            ),
            payments=[
                _make_payment(
                    amount="60.00",
                    vat_amount="10.00",
                    vat_rate="20.00",
                    include_vat=True,
                ),
            ],
        ),
    ]

    check.total_amount_field = _make_total_amount_field(
        total=total_payment,
        taxes=taxes,
    )
    check.advance_payments_field = AdvancePaymentsField(value=advances, sources=[])
    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.success
    assert result.errors == []


async def test_check_nds_fails_when_formula_is_incorrect() -> None:
    bad_vat = str(Decimal("20.00") + AMOUNT_TOLERANCE + Decimal("0.01"))
    check = CheckTaxesValidation(tolerance=AMOUNT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount=bad_vat,
        vat_rate="20.00",
        include_vat=True,
    )
    taxes = [
        _make_payment(
            amount="120.00",
            vat_amount=bad_vat,
            vat_rate="20.00",
            include_vat=True,
        ),
    ]

    check.total_amount_field = _make_total_amount_field(
        total=total_payment,
        taxes=taxes,
    )
    check.advance_payments_field = None
    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.failed
    assert any(
        isinstance(error, VatAmountCalculationDiscrepancyError)
        for error in result.errors
    )


async def test_check_nds_fails_when_total_and_taxes_vat_sums_differ() -> None:
    check = CheckTaxesValidation(tolerance=AMOUNT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="20.00",
        vat_rate="20.00",
        include_vat=True,
    )
    taxes = [
        _make_payment(
            amount="60.00",
            vat_amount="10.00",
            vat_rate="20.00",
            include_vat=True,
        ),
    ]

    check.total_amount_field = _make_total_amount_field(
        total=total_payment,
        taxes=taxes,
    )
    check.advance_payments_field = None
    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.failed
    assert any(isinstance(error, VatAmountDiscrepancyError) for error in result.errors)


async def test_check_nds_compares_sums_even_when_amount_is_missing() -> None:
    check = CheckTaxesValidation(tolerance=AMOUNT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="20.00",
        vat_rate="20.00",
        include_vat=True,
    )
    taxes = [
        _make_payment(
            amount="120.00",
            vat_amount="20.00",
            vat_rate="20.00",
            include_vat=True,
        ),
    ]
    advances = [
        AdvancePayment(
            percent=Decimal("100.00"),
            total=_make_payment(
                amount=None,
                vat_amount="20.00",
                vat_rate="20.00",
                include_vat=True,
            ),
            payments=[
                _make_payment(
                    amount=None,
                    vat_amount="20.00",
                    vat_rate="20.00",
                    include_vat=True,
                ),
            ],
        ),
    ]

    check.total_amount_field = _make_total_amount_field(
        total=total_payment,
        taxes=taxes,
    )
    check.advance_payments_field = AdvancePaymentsField(value=advances, sources=[])
    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.success
    assert not any(
        isinstance(error, VatAmountCalculationDiscrepancyError)
        for error in result.errors
    )


async def test_check_nds_succeeds_when_vat_is_not_included_and_formula_is_correct() -> (
    None
):
    check = CheckTaxesValidation(tolerance=AMOUNT_TOLERANCE)
    total_payment = _make_payment(
        amount="100.00",
        vat_amount="20.00",
        vat_rate="20.00",
        include_vat=False,
    )
    taxes = [
        _make_payment(
            amount="100.00",
            vat_amount="20.00",
            vat_rate="20.00",
            include_vat=False,
        ),
    ]

    check.total_amount_field = _make_total_amount_field(
        total=total_payment,
        taxes=taxes,
    )
    check.advance_payments_field = None
    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.success
    assert result.errors == []


async def test_check_nds_tolerance_allows_difference_within_one_ruble() -> None:
    within_tolerance = str(Decimal("20.00") + AMOUNT_TOLERANCE - Decimal("0.01"))
    check = CheckTaxesValidation(tolerance=AMOUNT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount=within_tolerance,
        vat_rate="20.00",
        include_vat=True,
    )
    taxes = [
        _make_payment(
            amount="120.00",
            vat_amount=within_tolerance,
            vat_rate="20.00",
            include_vat=True,
        ),
    ]

    check.total_amount_field = _make_total_amount_field(
        total=total_payment,
        taxes=taxes,
    )
    check.advance_payments_field = None
    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.success
    assert not any(
        isinstance(error, VatAmountCalculationDiscrepancyError)
        for error in result.errors
    )


async def test_check_nds_tolerance_fails_when_difference_exceeds_one_ruble() -> None:
    over_tolerance = str(Decimal("20.00") + AMOUNT_TOLERANCE + Decimal("0.01"))
    check = CheckTaxesValidation(tolerance=AMOUNT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount=over_tolerance,
        vat_rate="20.00",
        include_vat=True,
    )
    taxes = [
        _make_payment(
            amount="120.00",
            vat_amount=over_tolerance,
            vat_rate="20.00",
            include_vat=True,
        ),
    ]

    check.total_amount_field = _make_total_amount_field(
        total=total_payment,
        taxes=taxes,
    )
    check.advance_payments_field = None
    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.failed
    assert any(
        isinstance(error, VatAmountCalculationDiscrepancyError)
        for error in result.errors
    )


async def test_check_nds_fails_when_amount_is_not_positive() -> None:
    check = CheckTaxesValidation(tolerance=AMOUNT_TOLERANCE)
    total_payment = _make_payment(
        amount="0.00",
        vat_amount="20.00",
        vat_rate="20.00",
        include_vat=True,
    )

    check.total_amount_field = _make_total_amount_field(
        total=total_payment,
        taxes=[],
    )
    check.advance_payments_field = None
    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.failed
    assert any(isinstance(error, AmountNotPositiveError) for error in result.errors)


async def test_check_nds_allows_zero_vat_amount() -> None:
    check = CheckTaxesValidation(tolerance=AMOUNT_TOLERANCE)
    total_payment = _make_payment(
        amount=None,
        vat_amount="0.00",
        vat_rate="20.00",
        include_vat=True,
    )

    check.total_amount_field = _make_total_amount_field(
        total=total_payment,
        taxes=[],
    )
    check.advance_payments_field = None
    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.success
    assert result.errors == []


async def test_check_nds_allows_zero_vat_rate() -> None:
    check = CheckTaxesValidation(tolerance=AMOUNT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="0.00",
        vat_rate="0.00",
        include_vat=True,
    )

    check.total_amount_field = _make_total_amount_field(
        total=total_payment,
        taxes=[],
    )
    check.advance_payments_field = None
    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.success
    assert result.errors == []


async def test_check_nds_ignores_empty_taxes_list() -> None:
    check = CheckTaxesValidation(tolerance=AMOUNT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="20.00",
        vat_rate="20.00",
        include_vat=True,
    )

    check.total_amount_field = _make_total_amount_field(
        total=total_payment,
        taxes=[],
    )
    check.advance_payments_field = None
    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.success
    assert not any(
        isinstance(error, VatAmountDiscrepancyError) for error in result.errors
    )


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


async def _run(
    *,
    total: Payment,
    taxes: list[Payment] | None = None,
    advances: list[AdvancePayment] | None = None,
    tolerance: Decimal = AMOUNT_TOLERANCE,
):
    check = CheckTaxesValidation(tolerance=tolerance)
    check.total_amount_field = _make_total_amount_field(total=total, taxes=taxes or [])
    check.advance_payments_field = (
        AdvancePaymentsField(value=advances, sources=[])
        if advances is not None
        else None
    )
    return await check.execute(STUB_CHECK_SERVICES)


async def test_check_nds_ignores_advances_without_totals_and_payments() -> None:
    check = CheckTaxesValidation(tolerance=AMOUNT_TOLERANCE)
    total_payment = _make_payment(
        amount="120.00",
        vat_amount="20.00",
        vat_rate="20.00",
        include_vat=True,
    )
    advances = [
        AdvancePayment(percent=Decimal("50.00"), total=None, payments=[]),
        AdvancePayment(percent=Decimal("50.00"), total=None, payments=[]),
    ]

    check.total_amount_field = _make_total_amount_field(
        total=total_payment,
        taxes=[],
    )
    check.advance_payments_field = AdvancePaymentsField(value=advances, sources=[])
    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.success
    assert not any(
        isinstance(error, VatAmountDiscrepancyError) for error in result.errors
    )


# --- VatAmountNotPositiveError / VatRateNotPositiveError ---


async def test_negative_vat_amount_fails() -> None:
    r = await _run(total=_pay(vat_amount="-5.00"))
    assert r.status == CheckStatus.failed
    assert any(isinstance(e, VatAmountNotPositiveError) for e in r.errors)


async def test_negative_vat_rate_fails() -> None:
    r = await _run(total=_pay(vat_rate="-20.00"))
    assert r.status == CheckStatus.failed
    assert any(isinstance(e, VatRateNotPositiveError) for e in r.errors)


# --- Отрицательный vat исключается из суммы ---


async def test_negative_vat_in_tax_excluded_from_sum_no_discrepancy() -> None:
    r = await _run(
        total=_pay(amount=None, vat_amount="20.00"),
        taxes=[_pay(amount=None, vat_amount="-5.00")],
    )
    assert r.status == CheckStatus.failed
    assert any(isinstance(e, VatAmountNotPositiveError) for e in r.errors)
    assert not any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)


# --- Несколько ошибок за один прогон ---


async def test_formula_error_and_sum_discrepancy_both_collected() -> None:
    bad_vat = str(Decimal("20.00") + AMOUNT_TOLERANCE + Decimal("0.01"))
    r = await _run(
        total=_pay(
            amount="120.00", vat_amount=bad_vat, vat_rate="20.00", include_vat=True
        ),
        taxes=[
            _pay(
                amount="120.00", vat_amount="20.00", vat_rate="20.00", include_vat=True
            )
        ],
    )
    assert r.status == CheckStatus.failed
    assert any(isinstance(e, VatAmountCalculationDiscrepancyError) for e in r.errors)
    assert any(isinstance(e, VatAmountDiscrepancyError) for e in r.errors)


# --- Discrepancy внутри аванса (aggregate vs payments sum) ---


async def test_advance_aggregate_vs_payments_sum_discrepancy_fails() -> None:
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


# --- Аванс без total использует сумму payments для cross-source ---


async def test_advance_without_total_payments_sum_matches_total_success() -> None:
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


async def test_advance_without_total_payments_sum_differs_from_total_fails() -> None:
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


# --- Несколько авансов суммируются для cross-source ---


async def test_multiple_advance_totals_summed_for_cross_source_success() -> None:
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


async def test_advance_total_vat_differs_from_contract_total_fails() -> None:
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
