from decimal import Decimal

import pytest

from contract_validation.checks.check_price_validation import CheckPriceValidation
from contract_validation.checks.errors import (
    InsufficientCheckDataError,
    MissingRequiredFieldError,
    MultiplyRequiredFieldError,
)
from contract_validation.constants import AMOUNT_TOLERANCE
from contract_validation.entities import (
    FieldCollector,
    Money,
    Payment,
    Source,
    Specification,
    SpecPosition,
    SpecPositionsField,
    TotalAmount,
    TotalAmountField,
    Vat,
    VatInclusion,
)
from contract_validation.entities.errors import (
    PositionCostDiscrepancyError,
    PositionsAmountDiscrepancyError,
)
from tests.conftest import StubDocument, run_check


def _make_payment(value: str) -> Payment:
    amount = Money(value=Decimal(value), transcription=None)
    return Payment(
        amount=amount,
        vat=Vat(amount=None, rate=None),
        include_vat=VatInclusion.UNSPECIFIED,
    )


def _make_total_amount_field(
    value: str,
    document: StubDocument,
) -> TotalAmountField:
    return TotalAmountField(
        value=TotalAmount(total=_make_payment(value), taxes=[]),
        sources=[Source(document_id=document.id)],
    )


async def test_check_price_validation_reports_no_errors_for_consistent_prices() -> None:
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=Specification(
                    [
                        SpecPosition(
                            name="Позиция 1",
                            quantity=Decimal("1.0"),
                            unit_price=Decimal("100.00"),
                            total_price=Decimal("100.00"),
                            unit_of_measurement="шт",
                        ),
                    ]
                ),
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("100.00", document),
        ],
    )

    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)

    result = await run_check(check, fields)

    assert result.errors == []


async def test_check_price_validation_raises_when_required_field_is_missing() -> None:
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=Specification(
                    [
                        SpecPosition(
                            name="Позиция 1",
                            quantity=Decimal("1.0"),
                            unit_price=Decimal("100.00"),
                            total_price=Decimal("100.00"),
                            unit_of_measurement="шт",
                        ),
                    ]
                ),
                sources=[Source(document_id=document.id)],
            ),
        ],
    )

    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)

    with pytest.raises(
        MissingRequiredFieldError,
        match="missing required field for 'total_amount_field'",
    ):
        await run_check(check, fields)


async def test_check_price_validation_raises_when_required_field_has_collision() -> (
    None
):
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=Specification(
                    [
                        SpecPosition(
                            name="Позиция 1",
                            quantity=Decimal("1.0"),
                            unit_price=Decimal("100.00"),
                            total_price=Decimal("100.00"),
                            unit_of_measurement="шт",
                        ),
                    ]
                ),
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("100.00", document),
            _make_total_amount_field("200.00", document),
        ],
    )

    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)

    with pytest.raises(
        MultiplyRequiredFieldError, match="collision for 'total_amount_field'"
    ):
        await run_check(check, fields)


async def test_check_price_validation_fails_when_position_total_mismatch() -> None:
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=Specification(
                    [
                        SpecPosition(
                            name="Позиция 1",
                            quantity=Decimal("5.0"),
                            unit_price=Decimal("100.00"),
                            total_price=Decimal("600.00"),  # должно быть 500.00
                            unit_of_measurement="шт",
                        ),
                    ]
                ),
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("600.00", document),
        ],
    )
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)

    result = await run_check(check, fields)

    called_errors = result.errors
    errors = [
        err for err in called_errors if isinstance(err, PositionCostDiscrepancyError)
    ]
    assert len(errors) == 1
    error = errors[0]
    assert error.quantity == Decimal("5.0")
    assert error.unit_price == Decimal("100.00")


async def test_check_price_validation_fails_when_total_amount_mismatch() -> None:
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=Specification(
                    [
                        SpecPosition(
                            name="Позиция 1",
                            quantity=Decimal("1.0"),
                            unit_price=Decimal("100.00"),
                            total_price=Decimal("100.00"),
                            unit_of_measurement="шт",
                        ),
                    ]
                ),
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("150.00", document),  # рассчитано 100.00
        ],
    )
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)

    result = await run_check(check, fields)

    called_errors = result.errors
    assert any(
        isinstance(err, PositionsAmountDiscrepancyError) for err in called_errors
    )


async def test_check_price_validation_succeeds_when_zero_values_are_consistent() -> (
    None
):
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=Specification(
                    [
                        SpecPosition(
                            name="Позиция 1",
                            quantity=Decimal("1.0"),
                            unit_price=Decimal("0.00"),
                            total_price=Decimal("0.00"),
                            unit_of_measurement="шт",
                        ),
                    ]
                ),
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("0.00", document),
        ],
    )
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)

    result = await run_check(check, fields)

    called_errors = result.errors
    assert called_errors == []


async def test_check_price_validation_skips_when_no_position_totals_to_compare() -> (
    None
):
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=Specification(
                    [
                        SpecPosition(
                            name="Услуга 1",
                            quantity=Decimal("6.0"),
                            unit_price=None,
                            total_price=None,
                            unit_of_measurement=None,
                        ),
                    ]
                ),
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("600000.0", document),
        ],
    )
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)

    with pytest.raises(
        InsufficientCheckDataError, match="cannot calculate positions total"
    ):
        await run_check(check, fields)


async def test_check_price_validation_skips_when_no_amounts_at_all() -> None:
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=Specification(
                    [
                        SpecPosition(
                            name="Позиция 1",
                            quantity=Decimal("1.0"),
                            unit_price=None,
                            total_price=None,
                            unit_of_measurement="шт",
                        ),
                    ]
                ),
                sources=[Source(document_id=document.id)],
            ),
            TotalAmountField(
                value=TotalAmount(
                    total=Payment(
                        amount=None,
                        vat=Vat(amount=None, rate=None),
                        include_vat=VatInclusion.UNSPECIFIED,
                    ),
                    taxes=[],
                ),
                sources=[Source(document_id=document.id)],
            ),
        ],
    )
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)
    check.prepare(fields)
    with pytest.raises(InsufficientCheckDataError):
        await check.execute()


async def test_check_price_validation_validates_positions_without_contract_total() -> (
    None
):
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=Specification(
                    [
                        SpecPosition(
                            name="Позиция 1",
                            quantity=Decimal("2.0"),
                            unit_price=Decimal("50.00"),
                            total_price=Decimal("100.00"),
                            unit_of_measurement="шт",
                        ),
                    ]
                ),
                sources=[Source(document_id=document.id)],
            ),
            TotalAmountField(
                value=TotalAmount(
                    total=Payment(
                        amount=None,
                        vat=Vat(amount=None, rate=None),
                        include_vat=VatInclusion.UNSPECIFIED,
                    ),
                    taxes=[],
                ),
                sources=[Source(document_id=document.id)],
            ),
        ],
    )
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)

    result = await run_check(check, fields)

    assert result.errors == []


async def test_check_price_validation_succeeds_when_within_tolerance() -> None:
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=Specification(
                    [
                        SpecPosition(
                            name="Позиция 1",
                            quantity=Decimal("1.0"),
                            unit_price=Decimal("100.00"),
                            total_price=Decimal("100.01"),  # ровно tolerance
                            unit_of_measurement="шт",
                        ),
                    ]
                ),
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("100.01", document),
        ],
    )
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)

    result = await run_check(check, fields)

    called_errors = result.errors
    assert called_errors == []


def _make_vat_total_amount_field(
    value: str,
    *,
    rate: str | None = None,
    vat_amount: str | None = None,
    include_vat: VatInclusion,
    document: StubDocument,
) -> TotalAmountField:
    total = Payment(
        amount=Money(value=Decimal(value), transcription=None),
        vat=Vat(
            amount=(
                Money(value=Decimal(vat_amount), transcription=None)
                if vat_amount is not None
                else None
            ),
            rate=Decimal(rate) if rate is not None else None,
        ),
        include_vat=include_vat,
    )
    return TotalAmountField(
        value=TotalAmount(total=total, taxes=[]),
        sources=[Source(document_id=document.id)],
    )


async def _run_price_check(fields: FieldCollector) -> list:
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)
    check.prepare(fields)
    result = await check.execute()
    return result.errors


async def test_check_price_validation_succeeds_when_positions_match_net_total() -> None:
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=Specification(
                    [
                        SpecPosition(
                            name="Позиция 1",
                            quantity=Decimal("1.0"),
                            unit_price=Decimal("100.00"),
                            total_price=Decimal("100.00"),
                            unit_of_measurement="шт",
                        ),
                    ]
                ),
                sources=[Source(document_id=document.id)],
            ),
            _make_vat_total_amount_field(
                "120.00",
                rate="20.00",
                include_vat=VatInclusion.INCLUDED,
                document=document,
            ),
        ],
    )

    errors = await _run_price_check(fields)

    assert errors == []


async def test_check_price_validation_uses_vat_amount_when_rate_is_missing() -> None:
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=Specification(
                    [
                        SpecPosition(
                            name="Позиция 1",
                            quantity=Decimal("1.0"),
                            unit_price=Decimal("100.00"),
                            total_price=Decimal("100.00"),
                            unit_of_measurement="шт",
                        ),
                    ]
                ),
                sources=[Source(document_id=document.id)],
            ),
            _make_vat_total_amount_field(
                "120.00",
                vat_amount="20.00",
                include_vat=VatInclusion.INCLUDED,
                document=document,
            ),
        ],
    )

    errors = await _run_price_check(fields)

    assert errors == []


async def test_check_price_validation_succeeds_when_positions_match_gross_total() -> (
    None
):
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=Specification(
                    [
                        SpecPosition(
                            name="Позиция 1",
                            quantity=Decimal("1.0"),
                            unit_price=Decimal("120.00"),
                            total_price=Decimal("120.00"),
                            unit_of_measurement="шт",
                        ),
                    ]
                ),
                sources=[Source(document_id=document.id)],
            ),
            _make_vat_total_amount_field(
                "100.00",
                rate="20.00",
                include_vat=VatInclusion.EXCLUDED,
                document=document,
            ),
        ],
    )

    errors = await _run_price_check(fields)

    assert errors == []
