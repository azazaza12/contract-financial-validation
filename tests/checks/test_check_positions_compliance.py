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
from app.domain.entities.validation import CheckStatus
from app.domain.pipeline.task import CheckTask, TaskStatus
from app.domain.service.checker import EvaluateResult
from tests.domain.pipeline.conftest import DummyContract, create_context


pytestmark = pytest.mark.asyncio


async def test_check1_can_run_as_task_and_save_result():
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            DocumentObjectField(
                value="Оборудование",
                sources=[Source(document=document)],
            ),
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=1.0,
                        unit_price=Decimal("100"),
                        total_price=Decimal("100"),
                        unit_of_measurement="шт",
                    )
                ],
                sources=[Source(document=document)],
            ),
        ]
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
    contract_repo.save_check_result = AsyncMock()
    ctx = create_context(
        contract=contract,
        contract_repo=contract_repo,
        check_position_compliance_service=position_service,
    )
    check = CheckPositionsCompliance()

    await CheckTask(check=check).run(ctx)

    contract_repo.save_check_result.assert_awaited_once()
    called_contract = contract_repo.save_check_result.call_args.kwargs["contract"]
    called_result = contract_repo.save_check_result.call_args.kwargs["result"]

    assert called_contract is contract
    assert called_result.check_name == "CheckPositionsCompliance"
    assert called_result.status == CheckStatus.success
    assert called_result.errors == []


async def test_check1_skips_when_required_field_is_missing():
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=1.0,
                        unit_price=Decimal("100"),
                        total_price=Decimal("100"),
                        unit_of_measurement="шт",
                    )
                ],
                sources=[Source(document=document)],
            ),
        ]
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
    contract_repo.save_check_result = AsyncMock()
    ctx = create_context(
        contract=contract,
        contract_repo=contract_repo,
        check_position_compliance_service=position_service,
    )
    check = CheckPositionsCompliance()

    await CheckTask(check=check).run(ctx)

    records = ctx.records_reg.records[ctx.pipeline.id]
    assert records[-1].status == TaskStatus.SKIPPED
    assert "missing required field for 'document_object_field'" in (
        records[-1].error_message or ""
    )
    contract_repo.save_check_result.assert_not_awaited()


async def test_check1_skips_when_required_field_has_collision():
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            DocumentObjectField(
                value="Оборудование",
                sources=[Source(document=document)],
            ),
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=1.0,
                        unit_price=Decimal("100"),
                        total_price=Decimal("100"),
                        unit_of_measurement="шт",
                    )
                ],
                sources=[Source(document=document)],
            ),
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 2",
                        quantity=2.0,
                        unit_price=Decimal("100"),
                        total_price=Decimal("200"),
                        unit_of_measurement="шт",
                    )
                ],
                sources=[Source(document=document)],
            ),
        ]
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
    contract_repo.save_check_result = AsyncMock()
    ctx = create_context(
        contract=contract,
        contract_repo=contract_repo,
        check_position_compliance_service=position_service,
    )
    check = CheckPositionsCompliance()

    await CheckTask(check=check).run(ctx)

    records = ctx.records_reg.records[ctx.pipeline.id]
    assert records[-1].status == TaskStatus.SKIPPED
    assert "collision for 'spec_positions_field'" in (records[-1].error_message or "")
    contract_repo.save_check_result.assert_not_awaited()
