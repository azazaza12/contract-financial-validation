from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.checks.check_number_transcription_rub import CheckNumberTranscriptionRub
from app.domain.checks.errors import InsufficientCheckDataError
from app.domain.entities import (
    AdvancePayment,
    AdvancePaymentList,
    AdvancePaymentsField,
    Money,
    Payment,
    PaymentList,
    Source,
    SourceHeader,
    TotalAmount,
    TotalAmountField,
    Vat,
)
from app.domain.entities.errors import NumberTranscriptionError
from app.domain.entities.single_supplier import SingleSupplierDocument
from app.domain.entities.validation import CheckStatus
from app.domain.ports.checker import TranscriptionCheckIssue


def _make_total_amount_field(value: str, transcription: str | None) -> TotalAmountField:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    return TotalAmountField(
        value=TotalAmount(
            total=Payment(
                amount=Money(value=Decimal(value), transcription=transcription),
                vat=Vat(amount=None, rate=None),
                include_vat=False,
            ),
            taxes=PaymentList([]),
        ),
        sources=[Source(document_id=document.id)],
    )


async def test_check_14_succeeds_when_no_transcription_issues() -> None:
    service_mock = AsyncMock()
    service_mock.evaluate.return_value = None
    check = CheckNumberTranscriptionRub(transcription_compliancer=service_mock)
    check.total_amount_fields = [
        _make_total_amount_field(
            value="100.00",
            transcription="Сто",
        )
    ]
    check.advance_payments_fields = []

    result = await check.execute()

    assert result.status == CheckStatus.SUCCESS
    assert result.errors == []
    service_mock.evaluate.assert_awaited_once()


async def test_check_14_maps_each_issue_to_validation_error() -> None:
    service_mock = AsyncMock()
    service_mock.evaluate.side_effect = [
        TranscriptionCheckIssue(
            value=Decimal("100.00"),
            transcription="Сто один",
            expected_transcription="Сто",
        ),
        TranscriptionCheckIssue(
            value=Decimal("20.00"),
            transcription="Двадцать один",
            expected_transcription="Двадцать",
        ),
    ]

    check = CheckNumberTranscriptionRub(
        transcription_compliancer=service_mock,
    )
    field_source = Source(document_id=uuid4(), header=SourceHeader.BODY)
    check.total_amount_fields = [
        TotalAmountField(
            value=TotalAmount(
                total=Payment(
                    amount=Money(value=Decimal("100.00"), transcription="Сто один"),
                    vat=Vat(
                        amount=Money(
                            value=Decimal("20.00"), transcription="Двадцать один"
                        ),
                        rate=Decimal("20.00"),
                    ),
                    include_vat=True,
                ),
                taxes=PaymentList([]),
            ),
            sources=[field_source],
        )
    ]
    check.advance_payments_fields = []

    result = await check.execute()

    assert result.status == CheckStatus.FAILED
    assert len(result.errors) == 2  # noqa: PLR2004
    first = result.errors[0]
    second = result.errors[1]
    assert isinstance(first, NumberTranscriptionError)
    assert isinstance(second, NumberTranscriptionError)
    assert first.index == 0
    assert first.value == Decimal("100.00")
    assert first.transcription == "Сто один"
    assert first.expected_transcription == "Сто"
    assert first.location is not None
    assert first.location.full_path == "TotalAmountField.value.total.amount.value"
    assert first.location.sources == (field_source,)
    assert second.index == 1
    assert second.value == Decimal("20.00")
    assert second.transcription == "Двадцать один"
    assert second.expected_transcription == "Двадцать"
    assert second.location is not None
    assert second.location.full_path == (
        "TotalAmountField.value.total.vat.amount.value"
    )
    assert second.location.sources == (field_source,)
    assert service_mock.evaluate.await_count == 2  # noqa: PLR2004


async def test_check_14_passes_each_nested_amount_to_service() -> None:
    service_mock = AsyncMock()
    service_mock.evaluate.return_value = None

    check = CheckNumberTranscriptionRub(
        transcription_compliancer=service_mock,
    )

    document = SingleSupplierDocument(id=uuid4(), file_name="contract.pdf")
    total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=Payment(
                amount=Money(
                    value=Decimal("1217291.25"),
                    transcription=(
                        "Один миллион двести семнадцать тысяч двести девяносто один"
                    ),
                ),
                vat=Vat(
                    amount=Money(
                        value=Decimal("200748.43"),
                        transcription="Двести тысяч семьсот сорок восемь",
                    ),
                    rate=Decimal("20.00"),
                ),
                include_vat=True,
            ),
            taxes=PaymentList([]),
        ),
        sources=[Source(document_id=document.id)],
    )
    advance_payments_field = AdvancePaymentsField(
        value=AdvancePaymentList(
            [
                AdvancePayment(
                    percent=Decimal("97.69"),
                    amount=Money(
                        value=Decimal("1189129.80"),
                        transcription=(
                            "Один миллион сто восемьдесят девять тысяч "
                            "сто двадцать девять"
                        ),
                    ),
                    vat=Vat(
                        amount=Money(
                            value=Decimal("198188.30"),
                            transcription=(
                                "Сто девяносто восемь тысяч сто восемьдесят восемь"
                            ),
                        ),
                        rate=Decimal("20.00"),
                    ),
                    include_vat=True,
                ),
                AdvancePayment(
                    percent=Decimal("2.31"),
                    amount=Money(
                        value=Decimal("28161.45"),
                        transcription="Двадцать восемь тысяч сто шестьдесят один",
                    ),
                    vat=Vat(
                        amount=Money(
                            value=Decimal("2560.13"),
                            transcription="Две тысячи пятьсот шестьдесят",
                        ),
                        rate=Decimal("10.00"),
                    ),
                    include_vat=True,
                ),
            ]
        ),
        sources=[Source(document_id=document.id)],
    )

    check.total_amount_fields = [total_amount_field]
    check.advance_payments_fields = [advance_payments_field]

    result = await check.execute()

    assert result.status == CheckStatus.SUCCESS
    assert service_mock.evaluate.await_count == 6  # noqa: PLR2004
    passed_pairs = {
        (call.args[0].value, call.args[0].transcription)
        for call in service_mock.evaluate.await_args_list
    }
    expected_pairs = {
        (
            Decimal("1217291.25"),
            "Один миллион двести семнадцать тысяч двести девяносто один",
        ),
        (Decimal("200748.43"), "Двести тысяч семьсот сорок восемь"),
        (
            Decimal("1189129.80"),
            "Один миллион сто восемьдесят девять тысяч сто двадцать девять",
        ),
        (
            Decimal("198188.30"),
            "Сто девяносто восемь тысяч сто восемьдесят восемь",
        ),
        (Decimal("28161.45"), "Двадцать восемь тысяч сто шестьдесят один"),
        (Decimal("2560.13"), "Две тысячи пятьсот шестьдесят"),
    }
    assert passed_pairs == expected_pairs


async def test_check_14_identifies_payment_and_advance_amounts() -> None:
    service_mock = AsyncMock()
    service_mock.evaluate.side_effect = lambda amount: TranscriptionCheckIssue(
        value=amount.value,
        transcription=amount.transcription,
        expected_transcription="Ожидаемое значение",
    )
    source = Source(document_id=uuid4(), header=SourceHeader.AFTER_SPEC)
    check = CheckNumberTranscriptionRub(transcription_compliancer=service_mock)
    check.total_amount_fields = [
        TotalAmountField(
            value=TotalAmount(
                total=Payment(
                    amount=None,
                    vat=Vat(amount=None, rate=None),
                    include_vat=False,
                ),
                taxes=PaymentList(
                    [
                        Payment(
                            amount=Money(value=Decimal(100), transcription="Сто"),
                            vat=Vat(
                                amount=Money(
                                    value=Decimal(20), transcription="Двадцать"
                                ),
                                rate=Decimal(20),
                            ),
                            include_vat=True,
                        )
                    ]
                ),
            ),
            sources=[source],
        )
    ]
    check.advance_payments_fields = [
        AdvancePaymentsField(
            value=AdvancePaymentList(
                [
                    AdvancePayment(
                        percent=Decimal(50),
                        amount=Money(value=Decimal(50), transcription="Пятьдесят"),
                        vat=Vat(
                            amount=Money(value=Decimal(10), transcription="Десять"),
                            rate=Decimal(20),
                        ),
                        include_vat=True,
                    )
                ]
            ),
            sources=[source],
        )
    ]

    result = await check.execute()

    assert [error.location.full_path for error in result.errors if error.location] == [
        "TotalAmountField.value.taxes._payments[0].amount.value",
        "TotalAmountField.value.taxes._payments[0].vat.amount.value",
        "AdvancePaymentsField.value._payments[0].amount.value",
        "AdvancePaymentsField.value._payments[0].vat.amount.value",
    ]
    assert all(
        error.location is not None and error.location.sources == (source,)
        for error in result.errors
    )


async def test_check_14_skips_when_no_amount_transcription_pairs() -> None:
    service_mock = AsyncMock()
    check = CheckNumberTranscriptionRub(transcription_compliancer=service_mock)
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    check.total_amount_fields = [
        TotalAmountField(
            value=TotalAmount(
                total=Payment(
                    amount=Money(value=None, transcription="Сто"),
                    vat=Vat(amount=None, rate=None),
                    include_vat=False,
                ),
                taxes=PaymentList([]),
            ),
            sources=[Source(document_id=document.id)],
        )
    ]
    check.advance_payments_fields = []

    with pytest.raises(InsufficientCheckDataError):
        await check.execute()

    service_mock.evaluate.assert_not_awaited()
