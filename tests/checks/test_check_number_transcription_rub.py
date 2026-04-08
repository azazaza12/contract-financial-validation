from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.domain.entities.validation_errors import NumberTranscriptionErrorCheckResult

from app.domain.checks.check_number_transcription_rub import (
    CheckNumberTranscriptionRub,
)
from app.domain.entities.merge_types import Source
from app.domain.entities.single_supplier import SingleSupplierDocument
from app.domain.entities.single_supplier_fields import (
    AdvancePayment,
    AdvancePaymentsField,
    Amount,
    Payment,
    TotalAmount,
    TotalAmountField,
    Vat,
)
from app.domain.entities.validation import CheckStatus
from app.domain.service.checker import TranscriptionCheckIssue, TranscriptionCheckResult


pytestmark = pytest.mark.asyncio


def _make_total_amount_field(value: str, transcription: str | None) -> TotalAmountField:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    return TotalAmountField(
        value=TotalAmount(
            total=Payment(
                amount=Amount(value=Decimal(value), transcription=transcription),
                vat=Vat(amount=None, rate=None),
                include_vat=False,
            ),
            taxes=None,
        ),
        sources=[Source(document=document)],
    )


async def test_check_14_succeeds_when_no_transcription_issues():
    service_mock = AsyncMock()
    service_mock.evaluate.return_value = TranscriptionCheckResult(issues=[])
    check = CheckNumberTranscriptionRub()

    result = await check.execute(
        total_amount_field=_make_total_amount_field(
            value="100.00",
            transcription="Сто",
        ),
        advance_payments_field=AdvancePaymentsField(value=[], sources=[]),
        check_transcription_compliance_service=service_mock,
    )

    assert result.status == CheckStatus.success
    assert result.errors == []
    service_mock.evaluate.assert_awaited_once()


async def test_check_14_maps_each_issue_to_validation_error():
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
        ]
    )
    check = CheckNumberTranscriptionRub()

    result = await check.execute(
        total_amount_field=_make_total_amount_field(
            value="100.00",
            transcription="Сто один",
        ),
        advance_payments_field=AdvancePaymentsField(value=[], sources=[]),
        check_transcription_compliance_service=service_mock,
    )

    assert result.status == CheckStatus.failed
    assert len(result.errors) == 2
    assert all(
        isinstance(error, NumberTranscriptionErrorCheckResult)
        for error in result.errors
    )
    assert result.errors[0].index == 1
    assert result.errors[0].value == Decimal("100.00")
    assert result.errors[0].transcription == "Сто один"
    assert result.errors[0].expected_transcription == "Сто"
    assert result.errors[1].index == 2
    assert result.errors[1].value == Decimal("200.00")
    service_mock.evaluate.assert_awaited_once()


async def test_check_14_passes_realistic_nested_amounts_to_service():
    service_mock = AsyncMock()
    service_mock.evaluate.return_value = TranscriptionCheckResult(issues=[])
    check = CheckNumberTranscriptionRub()

    document = SingleSupplierDocument(id=uuid4(), file_name="contract.pdf")
    total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=Payment(
                amount=Amount(
                    value=Decimal("1217291.25"),
                    transcription=(
                        "Один миллион двести семнадцать тысяч двести девяносто один"
                    ),
                ),
                vat=Vat(
                    amount=Amount(
                        value=Decimal("200748.43"),
                        transcription="Двести тысяч семьсот сорок восемь",
                    ),
                    rate=Decimal("20.00"),
                ),
                include_vat=True,
            ),
            taxes=None,
        ),
        sources=[Source(document=document)],
    )
    advance_payments_field = AdvancePaymentsField(
        value=[
            AdvancePayment(
                percent=Decimal("97.69"),
                total=Payment(
                    amount=Amount(
                        value=Decimal("1189129.80"),
                        transcription=(
                            "Один миллион сто восемьдесят девять тысяч "
                            "сто двадцать девять"
                        ),
                    ),
                    vat=Vat(
                        amount=Amount(
                            value=Decimal("198188.30"),
                            transcription=(
                                "Сто девяносто восемь тысяч сто восемьдесят восемь"
                            ),
                        ),
                        rate=Decimal("20.00"),
                    ),
                    include_vat=True,
                ),
                payments=None,
            ),
            AdvancePayment(
                percent=Decimal("2.31"),
                total=Payment(
                    amount=Amount(
                        value=Decimal("28161.45"),
                        transcription="Двадцать восемь тысяч сто шестьдесят один",
                    ),
                    vat=Vat(
                        amount=Amount(
                            value=Decimal("2560.13"),
                            transcription="Две тысячи пятьсот шестьдесят",
                        ),
                        rate=Decimal("10.00"),
                    ),
                    include_vat=True,
                ),
                payments=None,
            ),
        ],
        sources=[Source(document=document)],
    )

    result = await check.execute(
        total_amount_field=total_amount_field,
        advance_payments_field=advance_payments_field,
        check_transcription_compliance_service=service_mock,
    )

    assert result.status == CheckStatus.success
    service_mock.evaluate.assert_awaited_once()
    passed_amounts = service_mock.evaluate.await_args.args[0]

    assert len(passed_amounts) == 6
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
