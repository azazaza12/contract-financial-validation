from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.domain.checks.check_positions_compliance import (
    CheckPositionsCompliance,
)
from app.domain.checks.deps import CheckServices
from app.domain.entities.field import FieldCollector
from app.domain.entities.merge_types import Source
from app.domain.entities.single_supplier import SingleSupplierDocument
from app.domain.entities.single_supplier_fields import (
    DocumentObjectField,
    SpecPosition,
    SpecPositionsField,
)
from app.domain.pipeline.task import CheckTask, TaskStatus
from app.domain.ports.checker import EvaluateResult

from tests.domain.pipeline.conftest import DummyContract, create_context


pytestmark = pytest.mark.asyncio


def _check_services(position_service: AsyncMock) -> CheckServices:
    return cast(
        "CheckServices",
        SimpleNamespace(
            check_position_compliance_service=position_service,
            check_transcription_compliance_service=MagicMock(),
        ),
    )


async def _run_check_task(
    *,
    document_object: str,
    positions: list[SpecPosition],
) -> tuple[MagicMock, object]:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            DocumentObjectField(
                value=document_object,
                sources=[Source(document_id=document.id)],
            ),
            SpecPositionsField(
                value=positions,
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
    await CheckTask(check=CheckPositionsCompliance()).run(ctx)
    run = await ctx.pipeline_run_repo.get_by_id(ctx.pipeline.id)
    return contract_repo, run


async def test_skips_when_document_object_is_blank() -> None:
    contract_repo, run = await _run_check_task(
        document_object="   ",
        positions=[
            SpecPosition(
                name="Позиция 1",
                quantity=None,
                unit_price=None,
                total_price=None,
                unit_of_measurement=None,
            ),
        ],
    )

    assert run.records[-1].status == TaskStatus.SKIPPED
    assert "no document object" in (run.records[-1].error_message or "")
    contract_repo.save_errors.assert_not_awaited()


async def test_skips_when_all_position_names_are_blank() -> None:
    contract_repo, run = await _run_check_task(
        document_object="Поставка оборудования",
        positions=[
            SpecPosition(
                name=None,
                quantity=Decimal(1),
                unit_price=None,
                total_price=None,
                unit_of_measurement=None,
            ),
            SpecPosition(
                name="",
                quantity=None,
                unit_price=None,
                total_price=None,
                unit_of_measurement=None,
            ),
            SpecPosition(
                name="  ",
                quantity=None,
                unit_price=None,
                total_price=None,
                unit_of_measurement=None,
            ),
        ],
    )

    assert run.records[-1].status == TaskStatus.SKIPPED
    assert "no position names" in (run.records[-1].error_message or "")
    contract_repo.save_errors.assert_not_awaited()


async def test_skips_when_position_list_is_empty() -> None:
    contract_repo, run = await _run_check_task(
        document_object="Поставка оборудования",
        positions=[],
    )

    assert run.records[-1].status == TaskStatus.SKIPPED
    assert "no position names" in (run.records[-1].error_message or "")
    contract_repo.save_errors.assert_not_awaited()


async def test_passes_stripped_position_names_to_compliance_service() -> None:
    position_service = AsyncMock()
    position_service.evaluate.return_value = EvaluateResult(
        success=True,
        text=None,
        error=None,
    )
    check = CheckPositionsCompliance()
    check.document_object_field = DocumentObjectField(
        value="  Поставка оборудования  ",
        sources=[],
    )
    check.spec_positions_field = SpecPositionsField(
        value=[
            SpecPosition(
                name="  Позиция 1  ",
                quantity=None,
                unit_price=None,
                total_price=None,
                unit_of_measurement=None,
            ),
            SpecPosition(
                name="",
                quantity=None,
                unit_price=None,
                total_price=None,
                unit_of_measurement=None,
            ),
        ],
        sources=[],
    )

    await check.execute(_check_services(position_service))

    position_service.evaluate.assert_awaited_once_with(
        "Поставка оборудования",
        ["Позиция 1"],
    )


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

    contract_repo.save_errors.assert_awaited_once_with(contract.id, [], kind="check")


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

    run = await ctx.pipeline_run_repo.get_by_id(ctx.pipeline.id)
    assert run.records[-1].status == TaskStatus.SKIPPED
    assert "missing required field for 'document_object_field'" in (
        run.records[-1].error_message or ""
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

    run = await ctx.pipeline_run_repo.get_by_id(ctx.pipeline.id)
    assert run.records[-1].status == TaskStatus.SKIPPED
    assert "collision for 'spec_positions_field'" in (
        run.records[-1].error_message or ""
    )
    contract_repo.save_errors.assert_not_awaited()
