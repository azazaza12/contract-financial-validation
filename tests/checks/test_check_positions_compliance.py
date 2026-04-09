from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.domain.checks.check_positions_compliance import (
    CheckPositionsCompliance,
)
from app.domain.checks.errors import (
    MissingRequiredFieldError,
    MultiplyRequiredFieldError,
)
from app.domain.entities.field import FieldCollector
from app.domain.entities.merge_types import Source
from app.domain.entities.single_supplier import (
    DocumentObjectField,
    SingleSupplierDocument,
    SpecPosition,
    SpecPositionsField,
)
from app.domain.entities.validation import CheckStatus
from app.domain.pipeline.task import CheckTask
from app.domain.service.checker import EvaluateResult
from tests.domain.pipeline.conftest import DummyContract, create_context


pytestmark = pytest.mark.asyncio


async def test_check1_can_run_as_task_and_save_result() -> None:
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
                        unit_price=Decimal(100),
                        total_price=Decimal(100),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document=document)],
            ),
        ],
    )

    contract = DummyContract(
        id=uuid4(),
        documents=[document],
        fields=fields,
        user_id="test-user",
        contract_name="contract.pdf",
        errors=[],
    )

    position_service = AsyncMock()
    position_service.evaluate.return_value = EvaluateResult(
        success=True,
        text=None,
        error=None,
    )
    check_result_repo = MagicMock()
    ctx = create_context(
        contract=contract,
        check_result_repo=check_result_repo,
        check_position_compliance_service=position_service,
    )
    check = CheckPositionsCompliance(ctx=ctx)

    await CheckTask(check=check).run(ctx)

    check_result_repo.save_for_contract.assert_called_once()
    called_contract = check_result_repo.save_for_contract.call_args.kwargs["contract"]
    called_result = check_result_repo.save_for_contract.call_args.kwargs["result"]

    assert called_contract is contract
    assert called_result.check_name == "CheckPositionsCompliance"
    assert called_result.status == CheckStatus.success
    assert called_result.errors == []


async def test_check1_raises_when_required_field_is_missing() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=1.0,
                        unit_price=Decimal(100),
                        total_price=Decimal(100),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document=document)],
            ),
        ],
    )
    contract = DummyContract(
        id=uuid4(),
        documents=[document],
        fields=fields,
        user_id="test-user",
        contract_name="contract.pdf",
        errors=[],
    )

    position_service = AsyncMock()
    check_result_repo = MagicMock()
    ctx = create_context(
        contract=contract,
        check_result_repo=check_result_repo,
        check_position_compliance_service=position_service,
    )
    check = CheckPositionsCompliance(ctx=ctx)

    with pytest.raises(MissingRequiredFieldError) as err:
        await CheckTask(check=check).run(ctx)

    assert err.value.check_name == "CheckPositionsCompliance"
    assert err.value.param_name == "document_object_field"
    check_result_repo.save_for_contract.assert_not_called()


async def test_check1_raises_when_required_field_has_collision() -> None:
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
                        unit_price=Decimal(100),
                        total_price=Decimal(100),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document=document)],
            ),
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 2",
                        quantity=2.0,
                        unit_price=Decimal(100),
                        total_price=Decimal(200),
                        unit_of_measurement="шт",
                    ),
                ],
                sources=[Source(document=document)],
            ),
        ],
    )
    contract = DummyContract(
        id=uuid4(),
        documents=[document],
        fields=fields,
        user_id="test-user",
        contract_name="contract.pdf",
        errors=[],
    )

    position_service = AsyncMock()
    check_result_repo = MagicMock()
    ctx = create_context(
        contract=contract,
        check_result_repo=check_result_repo,
        check_position_compliance_service=position_service,
    )
    check = CheckPositionsCompliance(ctx=ctx)

    with pytest.raises(MultiplyRequiredFieldError) as err:
        await CheckTask(check=check).run(ctx)

    assert err.value.check_name == "CheckPositionsCompliance"
    assert err.value.param_name == "spec_positions_field"
    assert err.value.count == 2  # noqa: PLR2004
    check_result_repo.save_for_contract.assert_not_called()
