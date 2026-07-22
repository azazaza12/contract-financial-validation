from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.checks.check_number_transcription_rub import CheckNumberTranscriptionRub
from app.domain.checks.errors import InsufficientCheckDataError
from app.domain.entities import (
    AdvancePayment,
    AdvancePaymentsField,
    Money,
    Payment,
    Source,
    TotalAmount,
    TotalAmountField,
    Vat,
)
from app.domain.entities.errors import NumberTranscriptionError
from app.domain.entities.single_supplier import SingleSupplierDocument
from app.domain.entities.validation import CheckStatus
from app.domain.ports.checker import TranscriptionCheckIssue, TranscriptionCheckResult


def _make_total_amount_field(value: str, transcription: str | None) -> TotalAmountField:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    return TotalAmountField(
        value=TotalAmount(
            total=Payment(
                amount=Money(value=Decimal(value), transcription=transcription),
                vat=Vat(amount=None, rate=None),
                include_vat=False,
            ),
            taxes=[],
        ),
        sources=[Source(document_id=document.id)],
    )


async def test_check_14_succeeds_when_no_transcription_issues() -> None:
    service_mock = AsyncMock()
    service_mock.evaluate.return_value = TranscriptionCheckResult(issues=[])
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
    service_mock.evaluate.return_value = TranscriptionCheckResult(
        issues=[
            TranscriptionCheckIssue(
                index=1,
                value=Decimal("100.00"),
                transcription="Сто один",
                expected_transcription="Сто",
            ),
            TranscriptionCheckIssue(
                index=2,
                value=Decimal("200.00"),
                transcription="Двести один",
                expected_transcription="Двести",
            ),
        ],
    )
    check = CheckNumberTranscriptionRub(transcription_compliancer=service_mock)
    check.total_amount_fields = [
        _make_total_amount_field(
            value="100.00",
            transcription="Сто один",
        )
    ]
    check.advance_payments_fields = []

    result = await check.execute()

    assert result.status == CheckStatus.FAILED
    assert len(result.errors) == 2  # noqa: PLR2004
    assert all(isinstance(error, NumberTranscriptionError) for error in result.errors)
    first = result.errors[0]
    second = result.errors[1]
    assert isinstance(first, NumberTranscriptionError)
    assert isinstance(second, NumberTranscriptionError)
    assert first.index == 1
    assert first.value == Decimal("100.00")
    assert first.transcription == "Сто один"
    assert first.expected_transcription == "Сто"
    assert second.index == 2  # noqa: PLR2004
    assert second.value == Decimal("200.00")
    service_mock.evaluate.assert_awaited_once()


async def test_check_14_passes_realistic_nested_amounts_to_service() -> None:
    service_mock = AsyncMock()
    service_mock.evaluate.return_value = TranscriptionCheckResult(issues=[])
    check = CheckNumberTranscriptionRub(transcription_compliancer=service_mock)

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
            taxes=[],
        ),
        sources=[Source(document_id=document.id)],
    )
    advance_payments_field = AdvancePaymentsField(
        value=[
            AdvancePayment(
                percent=Decimal("97.69"),
                total=Payment(
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
                payments=[],
            ),
            AdvancePayment(
                percent=Decimal("2.31"),
                total=Payment(
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
                payments=[],
            ),
        ],
        sources=[Source(document_id=document.id)],
    )

    check.total_amount_fields = [total_amount_field]
    check.advance_payments_fields = [advance_payments_field]

    result = await check.execute()

    assert result.status == CheckStatus.SUCCESS
    service_mock.evaluate.assert_awaited_once()
    passed_amounts = service_mock.evaluate.await_args.args[0]

    assert len(passed_amounts) == 6  # noqa: PLR2004
    actual_pairs = {(amount.value, amount.transcription) for amount in passed_amounts}
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
    assert actual_pairs == expected_pairs


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
                taxes=[],
            ),
            sources=[Source(document_id=document.id)],
        )
    ]
    check.advance_payments_fields = []

    with pytest.raises(InsufficientCheckDataError):
        await check.execute()

    service_mock.evaluate.assert_not_awaited()
