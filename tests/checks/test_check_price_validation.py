from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest


pytestmark = pytest.mark.asyncio

DEFAULT_TOLERANCE = Decimal("0.01")

from app.domain.checks.check_price_validation import CheckPriceValidation
from app.domain.checks.errors import (
    MissingRequiredFieldError,
    MultiplyRequiredFieldError,
)
from app.domain.entities.field import FieldCollector
from app.domain.entities.merge_types import Source
from app.domain.entities.single_supplier import (
    Amount,
    Payment,
    SingleSupplierDocument,
    SpecPosition,
    SpecPositionsField,
    TotalAmount,
    TotalAmountField,
    Vat,
)
from app.domain.entities.validation import CheckStatus
from app.domain.entities.validation_errors import (
    AmountDiscrepancyCheckResult,
    AmountNotPositiveCheckResult,
    PositionCostDiscrepancyCheckResult,
)
from app.domain.pipeline.task import CheckTask
from tests.domain.pipeline.conftest import DummyContract, create_context


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
        value=TotalAmount(total=_make_payment(value), taxes=None),
        sources=[Source(document=document)],
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
        errors=[],
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
                sources=[Source(document=document)],
            ),
            _make_total_amount_field("100.00", document),
        ]
    )

    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=DEFAULT_TOLERANCE)
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)

    await CheckTask(check=check).run(ctx)

    check_result_repo.save_for_contract.assert_called_once()
    called_contract = check_result_repo.save_for_contract.call_args.kwargs["contract"]
    called_result = check_result_repo.save_for_contract.call_args.kwargs["result"]

    assert called_contract is contract
    assert called_result.check_name == "CheckPriceValidation"
    assert called_result.status == CheckStatus.success
    assert called_result.errors == []


async def test_check_price_validation_raises_when_required_field_is_missing():
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
                sources=[Source(document=document)],
            ),
        ]
    )

    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=DEFAULT_TOLERANCE)
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)

    with pytest.raises(MissingRequiredFieldError) as err:
        await CheckTask(check=check).run(ctx)

    assert err.value.check_name == "CheckPriceValidation"
    assert err.value.param_name == "total_amount_field"
    check_result_repo.save_for_contract.assert_not_called()


async def test_check_price_validation_raises_when_required_field_has_collision():
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
                sources=[Source(document=document)],
            ),
            _make_total_amount_field("100.00", document),
            _make_total_amount_field("200.00", document),
        ]
    )

    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=DEFAULT_TOLERANCE)
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)

    with pytest.raises(MultiplyRequiredFieldError) as err:
        await CheckTask(check=check).run(ctx)

    assert err.value.check_name == "CheckPriceValidation"
    assert err.value.param_name == "total_amount_field"
    assert err.value.count == 2
    check_result_repo.save_for_contract.assert_not_called()


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
                sources=[Source(document=document)],
            ),
            _make_total_amount_field("600.00", document),
        ]
    )
    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=DEFAULT_TOLERANCE)
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)

    await CheckTask(check=check).run(ctx)

    called_result = check_result_repo.save_for_contract.call_args.kwargs["result"]
    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, PositionCostDiscrepancyCheckResult)
        for err in called_result.errors
    )


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
                sources=[Source(document=document)],
            ),
            _make_total_amount_field("150.00", document),  # рассчитано 100.00
        ]
    )
    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=DEFAULT_TOLERANCE)
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)

    await CheckTask(check=check).run(ctx)

    called_result = check_result_repo.save_for_contract.call_args.kwargs["result"]
    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, AmountDiscrepancyCheckResult) for err in called_result.errors
    )


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
                sources=[Source(document=document)],
            ),
            _make_total_amount_field("0.00", document),
        ]
    )
    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=DEFAULT_TOLERANCE)
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)

    await CheckTask(check=check).run(ctx)

    called_result = check_result_repo.save_for_contract.call_args.kwargs["result"]
    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, AmountNotPositiveCheckResult) for err in called_result.errors
    )


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
                sources=[Source(document=document)],
            ),
            _make_total_amount_field("100.01", document),
        ]
    )
    contract = _make_contract(document, fields)
    check = CheckPriceValidation(tolerance=DEFAULT_TOLERANCE)
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)

    await CheckTask(check=check).run(ctx)

    called_result = check_result_repo.save_for_contract.call_args.kwargs["result"]
    assert called_result.status == CheckStatus.success
