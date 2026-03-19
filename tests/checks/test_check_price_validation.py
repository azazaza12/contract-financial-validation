import asyncio
from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.domain.entities.contract import BaseContract
from app.domain.entities.field import FieldCollector
from app.domain.entities.merge_types import Source
from app.domain.entities.single_supplier import (
    Amount,
    Payment,
    SingleSupplierDocument,
    SpecPosition,
    SpecPositionsField,
    TotalAmountField,
)
from app.domain.entities.validation import CheckStatus
from app.domain.entities.validation_errors import (
    AmountDiscrepancyCheckResult,
    AmountNotPositiveCheckResult,
    PositionCostDiscrepancyCheckResult,
)
from app.domain.pipeline.task import CheckTask
from app.domain.service.checks.check_price_validation import CheckPriceValidation
from app.domain.service.checks.errors import (
    MissingRequiredFieldError,
    MultiplyRequiredFieldError,
)
from tests.domain.pipeline.conftest import create_context


@dataclass(kw_only=True)
class DummyContract(BaseContract):
    def build_pipeline(self, pipeline):
        return pipeline


def _make_payment(value: str) -> Payment:
    return Payment(
        amount=Amount(value=Decimal(value), transcription=None),
        vat_list=[],
        include_vat=False,
    )


def test_check_price_validation_can_run_as_task_and_save_result():
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=1.0,
                        unit_price=Decimal("100.00"),
                        total_price=Decimal("100.00"),
                        unit_of_measurement="шт",
                    )
                ],
                sources=[Source(document=document)],
            ),
            TotalAmountField(
                value=_make_payment("100.00"),
                sources=[Source(document=document)],
            ),
        ]
    )

    contract = DummyContract(
        id=uuid4(),
        file_name="contract.pdf",
        documents=[document],
        fields=fields,
        errors=[],
    )
    check = CheckPriceValidation()
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)

    asyncio.run(CheckTask(check=check).run(ctx))

    check_result_repo.save_for_contract.assert_called_once()
    called_contract = check_result_repo.save_for_contract.call_args.kwargs["contract"]
    called_result = check_result_repo.save_for_contract.call_args.kwargs["result"]

    assert called_contract is contract
    assert called_result.check_name == "CheckPriceValidation"
    assert called_result.status == CheckStatus.success
    assert called_result.errors == []


def test_check_price_validation_raises_when_required_field_is_missing():
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=1.0,
                        unit_price=Decimal("100.00"),
                        total_price=Decimal("100.00"),
                        unit_of_measurement="шт",
                    )
                ],
                sources=[Source(document=document)],
            ),
        ]
    )

    contract = DummyContract(
        id=uuid4(),
        file_name="contract.pdf",
        documents=[document],
        fields=fields,
        errors=[],
    )
    check = CheckPriceValidation()
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)

    with pytest.raises(MissingRequiredFieldError) as err:
        asyncio.run(CheckTask(check=check).run(ctx))

    assert err.value.check_name == "CheckPriceValidation"
    assert err.value.param_name == "total_amount_field"
    check_result_repo.save_for_contract.assert_not_called()


def test_check_price_validation_raises_when_required_field_has_collision():
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=1.0,
                        unit_price=Decimal("100.00"),
                        total_price=Decimal("100.00"),
                        unit_of_measurement="шт",
                    )
                ],
                sources=[Source(document=document)],
            ),
            TotalAmountField(
                value=_make_payment("100.00"),
                sources=[Source(document=document)],
            ),
            TotalAmountField(
                value=_make_payment("200.00"),
                sources=[Source(document=document)],
            ),
        ]
    )

    contract = DummyContract(
        id=uuid4(),
        file_name="contract.pdf",
        documents=[document],
        fields=fields,
        errors=[],
    )
    check = CheckPriceValidation()
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)

    with pytest.raises(MultiplyRequiredFieldError) as err:
        asyncio.run(CheckTask(check=check).run(ctx))

    assert err.value.check_name == "CheckPriceValidation"
    assert err.value.param_name == "total_amount_field"
    assert err.value.count == 2
    check_result_repo.save_for_contract.assert_not_called()


def test_check_price_validation_fails_when_position_total_mismatch():
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=5.0,
                        unit_price=Decimal("100.00"),
                        total_price=Decimal("600.00"),  # должно быть 500.00
                        unit_of_measurement="шт",
                    )
                ],
                sources=[Source(document=document)],
            ),
            TotalAmountField(
                value=_make_payment("600.00"),
                sources=[Source(document=document)],
            ),
        ]
    )
    contract = DummyContract(
        id=uuid4(),
        file_name="contract.pdf",
        documents=[document],
        fields=fields,
        errors=[],
    )
    check = CheckPriceValidation()
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)

    asyncio.run(CheckTask(check=check).run(ctx))

    called_result = check_result_repo.save_for_contract.call_args.kwargs["result"]
    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, PositionCostDiscrepancyCheckResult)
        for err in called_result.errors
    )


def test_check_price_validation_fails_when_total_amount_mismatch():
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=1.0,
                        unit_price=Decimal("100.00"),
                        total_price=Decimal("100.00"),
                        unit_of_measurement="шт",
                    )
                ],
                sources=[Source(document=document)],
            ),
            TotalAmountField(
                value=_make_payment("150.00"),  # рассчитано 100.00
                sources=[Source(document=document)],
            ),
        ]
    )
    contract = DummyContract(
        id=uuid4(),
        file_name="contract.pdf",
        documents=[document],
        fields=fields,
        errors=[],
    )
    check = CheckPriceValidation()
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)

    asyncio.run(CheckTask(check=check).run(ctx))

    called_result = check_result_repo.save_for_contract.call_args.kwargs["result"]
    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, AmountDiscrepancyCheckResult)
        for err in called_result.errors
    )


def test_check_price_validation_fails_when_values_not_positive():
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=1.0,
                        unit_price=Decimal("0.00"),
                        total_price=Decimal("0.00"),
                        unit_of_measurement="шт",
                    )
                ],
                sources=[Source(document=document)],
            ),
            TotalAmountField(
                value=_make_payment("0.00"),
                sources=[Source(document=document)],
            ),
        ]
    )
    contract = DummyContract(
        id=uuid4(),
        file_name="contract.pdf",
        documents=[document],
        fields=fields,
        errors=[],
    )
    check = CheckPriceValidation()
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)

    asyncio.run(CheckTask(check=check).run(ctx))

    called_result = check_result_repo.save_for_contract.call_args.kwargs["result"]
    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, AmountNotPositiveCheckResult)
        for err in called_result.errors
    )


def test_check_price_validation_succeeds_when_within_tolerance():
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            SpecPositionsField(
                value=[
                    SpecPosition(
                        name="Позиция 1",
                        quantity=1.0,
                        unit_price=Decimal("100.00"),
                        total_price=Decimal("100.01"),  # ровно tolerance
                        unit_of_measurement="шт",
                    )
                ],
                sources=[Source(document=document)],
            ),
            TotalAmountField(
                value=_make_payment("100.01"),
                sources=[Source(document=document)],
            ),
        ]
    )
    contract = DummyContract(
        id=uuid4(),
        file_name="contract.pdf",
        documents=[document],
        fields=fields,
        errors=[],
    )
    check = CheckPriceValidation()
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)

    asyncio.run(CheckTask(check=check).run(ctx))

    called_result = check_result_repo.save_for_contract.call_args.kwargs["result"]
    assert called_result.status == CheckStatus.success
