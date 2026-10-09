from decimal import Decimal

import pytest

from contract_validation.checks.check_payment_percent_validation import (
    CheckPaymentPercentValidation,
)
from contract_validation.checks.errors import InsufficientCheckDataError
from contract_validation.constants import AMOUNT_TOLERANCE
from contract_validation.entities import (
    EMPTY_PAYMENT,
    AdvancePayment,
    AdvancePaymentList,
    AdvancePaymentsField,
    FieldCollector,
    Money,
    Payment,
    Source,
    TotalAmount,
    TotalAmountField,
    Vat,
    VatInclusion,
)
from contract_validation.entities.errors import (
    PaymentAmountPercentDiscrepancyError,
    PaymentPercentSumDiscrepancyError,
)
from contract_validation.entities.validation import CheckStatus
from tests.conftest import StubDocument, run_check


def _make_payment(value: str, vat_rate: str = "20.00") -> Payment:
    amount = Money(value=Decimal(value), transcription=None)
    return Payment(
        amount=amount,
        vat=Vat(amount=amount, rate=Decimal(vat_rate)),
        include_vat=VatInclusion.INCLUDED,
    )


def _advance(*, percent: Decimal | None, total: Payment | None) -> AdvancePayment:
    base = total if total is not None else EMPTY_PAYMENT
    return AdvancePayment(
        percent=percent,
        amount=base.amount,
        vat=base.vat,
        include_vat=base.include_vat,
    )


def _make_advance(
    *,
    percent: Decimal | None,
    payment_value: str | None,
) -> AdvancePayment:
    total = _make_payment(payment_value) if payment_value is not None else None
    return _advance(percent=percent, total=total)


async def _run_check(*, total_amount: str | None, advances: list[AdvancePayment]):
    document = StubDocument(file_name="doc-1.pdf")
    if total_amount is not None:
        total_payment = _make_payment(total_amount)
    else:
        total_payment = Payment(
            amount=None,
            vat=Vat(amount=None, rate=Decimal("20.00")),
            include_vat=VatInclusion.INCLUDED,
        )
    total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=total_payment,
            taxes=[],
        ),
        sources=[Source(document_id=document.id)],
    )
    advance_payments_field = AdvancePaymentsField(
        value=AdvancePaymentList(advances),
        sources=[Source(document_id=document.id)],
    )
    fields = FieldCollector([total_amount_field, advance_payments_field])
    check = CheckPaymentPercentValidation(tolerance=AMOUNT_TOLERANCE)

    result = await run_check(check, fields)

    return result.errors


async def test_payment_percent_validates_amount_even_when_percents_missing() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="40.00"),
            _make_advance(percent=None, payment_value="60.00"),
        ],
    )

    assert any(
        isinstance(err, PaymentAmountPercentDiscrepancyError) for err in called_errors
    )
    assert any(
        isinstance(err, PaymentPercentSumDiscrepancyError) for err in called_errors
    )


async def test_payment_percent_validates_percent_sum_when_all_percents_are_specified() -> (  # noqa: E501
    None
):
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
        ],
    )

    assert any(
        isinstance(err, PaymentPercentSumDiscrepancyError) for err in called_errors
    )


async def test_payment_percent_succeeds_for_valid_percent_distribution() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_errors == []


async def test_payment_percent_succeeds_for_valid_three_payments() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
            _make_advance(percent=Decimal("40.00"), payment_value="40.00"),
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
        ],
    )

    assert called_errors == []


async def test_payment_percent_fails_when_amount_does_not_match_percent() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="60.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert any(
        isinstance(err, PaymentAmountPercentDiscrepancyError) for err in called_errors
    )


async def test_payment_percent_succeeds_when_percent_sum_difference_within_tolerance() -> (  # noqa: E501
    None
):
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("49.99"), payment_value="49.99"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_errors == []


async def test_payment_percent_succeeds_when_amount_difference_within_tolerance() -> (
    None
):
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(
                percent=Decimal("50.00"),
                payment_value=str(
                    Decimal("50.00") + AMOUNT_TOLERANCE - Decimal("0.01")
                ),
            ),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_errors == []


async def test_payment_percent_fails_when_amount_difference_exceeds_tolerance() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(
                percent=Decimal("50.00"),
                payment_value=str(
                    Decimal("50.00") + AMOUNT_TOLERANCE + Decimal("0.01")
                ),
            ),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert any(
        isinstance(err, PaymentAmountPercentDiscrepancyError) for err in called_errors
    )


async def test_payment_percent_skips_when_advance_list_is_empty() -> None:
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            TotalAmountField(
                value=TotalAmount(
                    total=_make_payment("100.00"),
                    taxes=[],
                ),
                sources=[Source(document_id=document.id)],
            ),
            AdvancePaymentsField(
                value=AdvancePaymentList([]),
                sources=[Source(document_id=document.id)],
            ),
        ],
    )
    check = CheckPaymentPercentValidation(tolerance=AMOUNT_TOLERANCE)

    with pytest.raises(InsufficientCheckDataError, match="no advance payment records"):
        await run_check(check, fields)


async def test_payment_percent_skips_when_no_advance_has_percent() -> None:
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            TotalAmountField(
                value=TotalAmount(
                    total=_make_payment("100.00"),
                    taxes=[],
                ),
                sources=[Source(document_id=document.id)],
            ),
            AdvancePaymentsField(
                value=AdvancePaymentList(
                    [
                        _make_advance(percent=None, payment_value="50.00"),
                        _make_advance(percent=None, payment_value="50.00"),
                    ]
                ),
                sources=[Source(document_id=document.id)],
            ),
        ],
    )
    check = CheckPaymentPercentValidation(tolerance=AMOUNT_TOLERANCE)

    with pytest.raises(InsufficientCheckDataError, match="no advance payment percents"):
        await run_check(check, fields)


async def test_payment_percent_succeeds_for_single_100_percent_payment() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[_make_advance(percent=Decimal("100.00"), payment_value="100.00")],
    )

    assert called_errors == []


async def test_payment_percent_can_return_multiple_errors() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="60.00"),
            _make_advance(percent=Decimal("30.00"), payment_value="10.00"),
        ],
    )

    assert len(called_errors) > 1
    assert any(
        isinstance(err, PaymentAmountPercentDiscrepancyError) for err in called_errors
    )
    assert any(
        isinstance(err, PaymentPercentSumDiscrepancyError) for err in called_errors
    )


async def test_payment_percent_sum_checked_when_contract_total_amount_missing() -> None:
    called_errors = await _run_check(
        total_amount=None,
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_errors == []


async def test_payment_percent_sum_fails_without_total_when_not_100() -> None:
    called_errors = await _run_check(
        total_amount=None,
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
        ],
    )

    assert any(
        isinstance(err, PaymentPercentSumDiscrepancyError) for err in called_errors
    )
    assert not any(
        isinstance(err, PaymentAmountPercentDiscrepancyError) for err in called_errors
    )


def _vat_payment(
    value: str,
    *,
    rate: str | None = None,
    vat_amount: str | None = None,
    include_vat: bool,
) -> Payment:
    return Payment(
        amount=Money(value=Decimal(value), transcription=None),
        vat=Vat(amount=None, rate=Decimal(rate)),
        include_vat=include_vat,
    )


async def test_payment_percent_falls_back_to_raw_when_advance_lacks_rate() -> None:
    document = StubDocument(file_name="doc-1.pdf")
    total_payment = _vat_payment(
        "100.00", rate="20.00", include_vat=VatInclusion.EXCLUDED
    )
    advances = [
        _advance(
            percent=Decimal("100.00"),
            total=Payment(
                amount=Money(value=Decimal("100.00"), transcription=None),
                vat=Vat(amount=None, rate=None),
                include_vat=VatInclusion.EXCLUDED,
            ),
        ),
    ]
    fields = FieldCollector(
        [
            TotalAmountField(
                value=TotalAmount(total=total_payment, taxes=[]),
                sources=[Source(document_id=document.id)],
            ),
            AdvancePaymentsField(
                value=AdvancePaymentList(advances),
                sources=[Source(document_id=document.id)],
            ),
        ],
    )
    check = CheckPaymentPercentValidation(tolerance=AMOUNT_TOLERANCE)
    check.prepare(fields)

    result = await check.execute()

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_payment_percent_succeeds_when_total_net_and_advances_gross_match() -> (
    None
):
    document = StubDocument(file_name="doc-1.pdf")
    total_payment = _vat_payment(
        "100.00", rate="20.00", include_vat=VatInclusion.EXCLUDED
    )
    advances = [
        _advance(
            percent=Decimal("50.00"),
            total=_vat_payment(
                "60.00", rate="20.00", include_vat=VatInclusion.INCLUDED
            ),
        ),
        _advance(
            percent=Decimal("50.00"),
            total=_vat_payment(
                "60.00", rate="20.00", include_vat=VatInclusion.INCLUDED
            ),
        ),
    ]
    fields = FieldCollector(
        [
            TotalAmountField(
                value=TotalAmount(total=total_payment, taxes=[]),
                sources=[Source(document_id=document.id)],
            ),
            AdvancePaymentsField(
                value=AdvancePaymentList(advances),
                sources=[Source(document_id=document.id)],
            ),
        ],
    )
    check = CheckPaymentPercentValidation(tolerance=AMOUNT_TOLERANCE)
    check.prepare(fields)

    result = await check.execute()

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []


async def test_payment_percent_falls_back_to_raw_amounts_without_common_basis() -> None:
    total_payment = Payment(
        amount=Money(value=Decimal("100.00"), transcription=None),
        vat=Vat(amount=None, rate=None),
        include_vat=VatInclusion.EXCLUDED,
    )
    advance = _advance(
        percent=Decimal("100.00"),
        total=Payment(
            amount=Money(value=Decimal("120.00"), transcription=None),
            vat=Vat(amount=None, rate=None),
            include_vat=VatInclusion.INCLUDED,
        ),
    )
    fields = FieldCollector(
        [
            TotalAmountField(
                value=TotalAmount(total=total_payment, taxes=[]),
                sources=[],
            ),
            AdvancePaymentsField(
                value=AdvancePaymentList([advance]),
                sources=[],
            ),
        ]
    )
    check = CheckPaymentPercentValidation(tolerance=AMOUNT_TOLERANCE)
    check.prepare(fields)

    result = await check.execute()

    assert result.status is CheckStatus.FAILED
    assert result.errors == [
        PaymentAmountPercentDiscrepancyError(
            amount=Decimal("120.00"),
            expected_amount=Decimal("100.00"),
            percent=Decimal("100.00"),
            contract_total_amount=Decimal("100.00"),
        )
    ]
