from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.domain.entities.errors import (
    AmountDiscrepancyError,
    AmountNotPositiveError,
    PositionCostDiscrepancyError,
)

from app.domain.checks.check_price_validation import CheckPriceValidation
from app.domain.entities.field import FieldCollector
from app.domain.entities.merge_types import Source
from app.domain.entities.single_supplier import SingleSupplierDocument
from app.domain.entities.single_supplier_fields import (
    Amount,
    Payment,
    SpecPosition,
    SpecPositionsField,
    TotalAmount,
    TotalAmountField,
    Vat,
)
from app.domain.pipeline.task import CheckTask, TaskStatus
from tests.domain.pipeline.conftest import DummyContract, create_context


pytestmark = pytest.mark.asyncio
DEFAULT_TOLERANCE = Decimal("0.01")


def _make_payment(value: str) -> Payment:
    amount = Amount(value=Decimal(value), transcription=None)
    return Payment(
        amount=amount,
        vat=Vat(amount=None, rate=None),
        include_vat=False,
    )


def _make_total_amount_field(
    value: str, document: SingleSupplierDocument
) -> TotalAmountField:
    return TotalAmountField(
        value=TotalAmount(total=_make_payment(value), taxes=[]),
        sources=[Source(document_id=document.id)],
    )


def _make_contract(
    document: SingleSupplierDocument, fields: FieldCollector
) -> DummyContract:
    return DummyContract(
        id=uuid4(),
        documents=[document],
        fields=fields,
        user_id="test-user",
        contract_name="contract.pdf",
    )


async def test_check_price_validation_can_run_as_task_and_save_result():
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
                    )
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("100.00", document),
        ]
    )

    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=DEFAULT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    contract_repo.save_errors.assert_awaited_once_with(
        contract, [], kind="check", source="CheckPriceValidation"
    )


async def test_check_price_validation_skips_when_required_field_is_missing():
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
                    )
                ],
                sources=[Source(document_id=document.id)],
            ),
        ]
    )

    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=DEFAULT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    records = await ctx.records_reg.get_all(ctx.pipeline.id)
    assert records[-1].status == TaskStatus.SKIPPED
    assert "missing required field for 'total_amount_field'" in (
        records[-1].error_message or ""
    )
    contract_repo.save_errors.assert_not_awaited()


async def test_check_price_validation_skips_when_required_field_has_collision():
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
                    )
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("100.00", document),
            _make_total_amount_field("200.00", document),
        ]
    )

    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=DEFAULT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    records = await ctx.records_reg.get_all(ctx.pipeline.id)
    assert records[-1].status == TaskStatus.SKIPPED
    assert "collision for 'total_amount_field'" in (records[-1].error_message or "")
    contract_repo.save_errors.assert_not_awaited()


async def test_check_price_validation_fails_when_position_total_mismatch():
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
                    )
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("600.00", document),
        ]
    )
    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=DEFAULT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    called_errors = contract_repo.save_errors.call_args.args[1]
    assert any(isinstance(err, PositionCostDiscrepancyError) for err in called_errors)


async def test_check_price_validation_fails_when_total_amount_mismatch():
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
                    )
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("150.00", document),  # рассчитано 100.00
        ]
    )
    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=DEFAULT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    called_errors = contract_repo.save_errors.call_args.args[1]
    assert any(isinstance(err, AmountDiscrepancyError) for err in called_errors)


async def test_check_price_validation_fails_when_values_not_positive():
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
                    )
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("0.00", document),
        ]
    )
    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=DEFAULT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    called_errors = contract_repo.save_errors.call_args.args[1]
    assert any(isinstance(err, AmountNotPositiveError) for err in called_errors)


async def test_check_price_validation_succeeds_when_within_tolerance():
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
                    )
                ],
                sources=[Source(document_id=document.id)],
            ),
            _make_total_amount_field("100.01", document),
        ]
    )
    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=DEFAULT_TOLERANCE)
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(check=check).run(ctx)

    called_errors = contract_repo.save_errors.call_args.args[1]
    assert called_errors == []
