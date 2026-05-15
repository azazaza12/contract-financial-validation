from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.domain.checks.check_positions_compliance import (
    CheckPositionsCompliance,
)
from app.domain.entities.field import FieldCollector
from app.domain.entities.merge_types import Source
from app.domain.entities.single_supplier import SingleSupplierDocument
from app.domain.entities.single_supplier_fields import (
    DocumentObjectField,
    SpecPosition,
    SpecPositionsField,
)
from app.domain.pipeline.task import CheckTask, TaskStatus
from app.domain.service.checker import EvaluateResult

from tests.domain.pipeline.conftest import DummyContract, create_context


pytestmark = pytest.mark.asyncio


async def test_check1_can_run_as_task_and_save_result() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            DocumentObjectField(
                value="Оборудование",
                sources=[Source(document_id=document.id)],
            ),
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=Decimal("1.00"),
                        unit_price=Decimal(100),
                        total_price=Decimal(100),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
        ],
    )

    contract = DummyContract(
        id=uuid4(),
        documents=[document],
        fields=fields,
        user_id="test-user",
        contract_name="contract.pdf",
    )

    position_service = AsyncMock()
    position_service.evaluate.return_value = EvaluateResult(
        success=True,
        text=None,
        error=None,
    )
    contract_repo = MagicMock()
    ctx = create_context(
        contract=contract,
        contract_repo=contract_repo,
        check_position_compliance_service=position_service,
    )
    check = CheckPositionsCompliance()

    await CheckTask(check=check).run(ctx)

    contract_repo.save_errors.assert_awaited_once_with(contract, [], kind="check")


async def test_check1_raises_when_required_field_is_missing() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=Decimal("1.00"),
                        unit_price=Decimal(100),
                        total_price=Decimal(100),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
        ],
    )
    contract = DummyContract(
        id=uuid4(),
        documents=[document],
        fields=fields,
        user_id="test-user",
        contract_name="contract.pdf",
    )

    position_service = AsyncMock()
    contract_repo = MagicMock()
    ctx = create_context(
        contract=contract,
        contract_repo=contract_repo,
        check_position_compliance_service=position_service,
    )
    check = CheckPositionsCompliance()

    await CheckTask(check=check).run(ctx)

    records = await ctx.pipeline_run_repo.find_task_records(ctx.pipeline.id)
    assert records[-1].status == TaskStatus.SKIPPED
    assert "missing required field for 'document_object_field'" in (
        records[-1].error_message or ""
    )
    contract_repo.save_errors.assert_not_awaited()


async def test_check1_raises_when_required_field_has_collision() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            DocumentObjectField(
                value="Оборудование",
                sources=[Source(document_id=document.id)],
            ),
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=Decimal("1.00"),
                        unit_price=Decimal(100),
                        total_price=Decimal(100),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 2",
                        quantity=Decimal("2.00"),
                        unit_price=Decimal(100),
                        total_price=Decimal(200),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document_id=document.id)],
            ),
        ],
    )
    contract = DummyContract(
        id=uuid4(),
        documents=[document],
        fields=fields,
        user_id="test-user",
        contract_name="contract.pdf",
    )

    position_service = AsyncMock()
    contract_repo = MagicMock()
    ctx = create_context(
        contract=contract,
        contract_repo=contract_repo,
        check_position_compliance_service=position_service,
    )
    check = CheckPositionsCompliance()

    await CheckTask(check=check).run(ctx)

    records = await ctx.pipeline_run_repo.find_task_records(ctx.pipeline.id)
    assert records[-1].status == TaskStatus.SKIPPED
    assert "collision for 'spec_positions_field'" in (records[-1].error_message or "")
    contract_repo.save_errors.assert_not_awaited()
