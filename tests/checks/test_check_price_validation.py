from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.domain.checks.check_price_validation import CheckPriceValidation
from app.domain.checks.errors import InsufficientCheckDataError
from app.domain.constants import AMOUNT_TOLERANCE
from app.domain.entities import (
    Money,
    FieldCollector,
    Payment,
    Source,
    SpecPosition,
    SpecPositionsField,
    TotalAmount,
    TotalAmountField,
    Vat,
)
from app.domain.entities.errors import (
    AmountDiscrepancyError,
    AmountNotPositiveError,
    PositionCostDiscrepancyError,
)
from app.domain.entities.single_supplier import SingleSupplierDocument
from app.domain.pipeline import TaskStatus
from app.domain.pipeline.task import CheckTask
from tests.domain.pipeline.conftest import DummyContract, create_context


def _make_payment(value: str) -> Payment:
    amount = Money(value=Decimal(value), transcription=None)
    return Payment(
        amount=amount,
        vat=Vat(amount=None, rate=None),
        include_vat=False,
    )


def _make_total_amount_field(
    value: str,
    document: SingleSupplierDocument,
) -> TotalAmountField:
    return TotalAmountField(
        value=TotalAmount(total=_make_payment(value), taxes=[]),
        sources=[Source(document_id=document.id)],
    )


def _make_contract(
    document: SingleSupplierDocument,
    fields: FieldCollector,
) -> DummyContract:
    return DummyContract(
        id=uuid4(),
        documents=[document],
        fields=fields,
        user_id="test-user",
        contract_name="contract.pdf",
    )


async def test_check_price_validation_can_run_as_task_and_save_result() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=Decimal("1.0"),
                        unit_price=Decimal("100.00"),
                        total_price=Decimal("100.00"),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("100.00", document),
        ],
    )

    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    contract_repo.save_errors.assert_awaited_once_with(contract.id, [], kind="check")


async def test_check_price_validation_raises_when_required_field_is_missing() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=Decimal("1.0"),
                        unit_price=Decimal("100.00"),
                        total_price=Decimal("100.00"),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
        ],
    )

    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    run = await ctx.pipeline_run_repo.get_by_id(ctx.pipeline.id)
    assert run.records[-1].status == TaskStatus.SKIPPED
    assert "missing required field for 'total_amount_field'" in (
        run.records[-1].error_message or ""
    )
    contract_repo.save_errors.assert_not_awaited()


async def test_check_price_validation_raises_when_required_field_has_collision() -> (
    None
):
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=Decimal("1.0"),
                        unit_price=Decimal("100.00"),
                        total_price=Decimal("100.00"),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("100.00", document),
            _make_total_amount_field("200.00", document),
        ],
    )

    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    run = await ctx.pipeline_run_repo.get_by_id(ctx.pipeline.id)
    assert run.records[-1].status == TaskStatus.SKIPPED
    assert "collision for 'total_amount_field'" in (run.records[-1].error_message or "")
    contract_repo.save_errors.assert_not_awaited()


async def test_check_price_validation_fails_when_position_total_mismatch() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=Decimal("5.0"),
                        unit_price=Decimal("100.00"),
                        total_price=Decimal("600.00"),  # должно быть 500.00
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("600.00", document),
        ],
    )
    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    called_errors = contract_repo.save_errors.call_args.args[1]
    assert any(isinstance(err, PositionCostDiscrepancyError) for err in called_errors)


async def test_check_price_validation_fails_when_total_amount_mismatch() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=Decimal("1.0"),
                        unit_price=Decimal("100.00"),
                        total_price=Decimal("100.00"),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("150.00", document),  # рассчитано 100.00
        ],
    )
    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    called_errors = contract_repo.save_errors.call_args.args[1]
    assert any(isinstance(err, AmountDiscrepancyError) for err in called_errors)


async def test_check_price_validation_fails_when_values_not_positive() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=Decimal("1.0"),
                        unit_price=Decimal("0.00"),
                        total_price=Decimal("0.00"),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("0.00", document),
        ],
    )
    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    called_errors = contract_repo.save_errors.call_args.args[1]
    assert any(isinstance(err, AmountNotPositiveError) for err in called_errors)


async def test_check_price_validation_skips_when_no_position_totals_to_compare() -> (
    None
):
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Кухонный рабочий",
                        quantity=Decimal("6.0"),
                        unit_price=None,
                        total_price=None,
                        unit_of_measurement=None,
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("6714000.0", document),
        ],
    )
    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    run = await ctx.pipeline_run_repo.get_by_id(ctx.pipeline.id)
    assert run.records[-1].status == TaskStatus.SKIPPED
    assert "cannot calculate positions total" in (run.records[-1].error_message or "")
    contract_repo.save_errors.assert_not_awaited()


async def test_check_price_validation_skips_when_no_amounts_at_all() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=Decimal("1.0"),
                        unit_price=None,
                        total_price=None,
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
            TotalAmountField(
                value=TotalAmount(
                    total=Payment(
                        amount=None,
                        vat=Vat(amount=None, rate=None),
                        include_vat=False,
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


async def test_check_price_validation_skips_when_contract_total_is_missing() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=Decimal("2.0"),
                        unit_price=Decimal("50.00"),
                        total_price=Decimal("100.00"),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
            TotalAmountField(
                value=TotalAmount(
                    total=Payment(
                        amount=None,
                        vat=Vat(amount=None, rate=None),
                        include_vat=False,
                    ),
                    taxes=[],
                ),
                sources=[Source(document_id=document.id)],
            ),
        ],
    )
    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    run = await ctx.pipeline_run_repo.get_by_id(ctx.pipeline.id)
    assert run.records[-1].status == TaskStatus.SKIPPED
    assert "no contract total amount" in (run.records[-1].error_message or "")
    contract_repo.save_errors.assert_not_awaited()


async def test_check_price_validation_succeeds_when_within_tolerance() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=Decimal("1.0"),
                        unit_price=Decimal("100.00"),
                        total_price=Decimal("100.01"),  # ровно tolerance
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("100.01", document),
        ],
    )
    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=AMOUNT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    called_errors = contract_repo.save_errors.call_args.args[1]
    assert called_errors == []


def _make_vat_total_amount_field(
    value: str,
    *,
    rate: str,
    include_vat: bool,
    document: SingleSupplierDocument,
) -> TotalAmountField:
    total = Payment(
        amount=Money(value=Decimal(value), transcription=None),
        vat=Vat(amount=None, rate=Decimal(rate)),
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
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=Decimal("1.0"),
                        unit_price=Decimal("100.00"),
                        total_price=Decimal("100.00"),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_vat_total_amount_field(
                "120.00", rate="20.00", include_vat=True, document=document
            ),
        ],
    )

    errors = await _run_price_check(fields)

    assert errors == []


async def test_check_price_validation_succeeds_when_positions_match_gross_total() -> (
    None
):
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=Decimal("1.0"),
                        unit_price=Decimal("120.00"),
                        total_price=Decimal("120.00"),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_vat_total_amount_field(
                "100.00", rate="20.00", include_vat=False, document=document
            ),
        ],
    )

    errors = await _run_price_check(fields)

    assert errors == []
