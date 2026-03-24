from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.domain.entities.field import FieldCollector
from app.domain.entities.merge_types import Source
from app.domain.entities.single_supplier import (
    AdvancePayment,
    AdvancePaymentsField,
    Amount,
    Payment,
    SingleSupplierDocument,
    TotalAmount,
    TotalAmountField,
    Vat,
)
from app.domain.entities.validation import CheckStatus
from app.domain.entities.validation_errors import (
    PaymentAmountPercentDiscrepancy,
    PaymentPercentSumDiscrepancyCheckResult,
)
from app.domain.pipeline.task import CheckTask
from app.domain.checks.check_payment_percent_validation import (
    CheckPaymentPercentValidation,
)
from tests.domain.pipeline.conftest import DummyContract, create_context

pytestmark = pytest.mark.asyncio


def _make_payment(value: str, vat_rate: str = "20.00") -> Payment:
    amount = Amount(value=Decimal(value), transcription=None)
    return Payment(
        amount=amount,
        vat=Vat(amount=amount, rate=Decimal(vat_rate)),
        include_vat=True,
    )


def _make_advance(
    *, percent: Decimal | None, payment_value: str | None
) -> AdvancePayment:
    total = _make_payment(payment_value) if payment_value is not None else None
    return AdvancePayment(percent=percent, total=total, payments=None)


async def _run_check(*, total_amount: str | None, advances: list[AdvancePayment]):
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    if total_amount is not None:
        total_payment = _make_payment(total_amount)
    else:
        total_payment = Payment(
            amount=None,
            vat=Vat(amount=None, rate=Decimal("20.00")),
            include_vat=True,
        )
    total_amount_field = TotalAmountField(
        value=TotalAmount(
            total=total_payment,
            taxes=None,
        ),
        sources=[Source(document=document)],
    )
    advance_payments_field = AdvancePaymentsField(
        value=advances,
        sources=[Source(document=document)],
    )
    contract = DummyContract(
        id=uuid4(),
        user_id="test-user",
        contract_name="contract.pdf",
        documents=[document],
        fields=FieldCollector([total_amount_field, advance_payments_field]),
        errors=[],
    )
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)
    check = CheckPaymentPercentValidation()

    await CheckTask(check=check).run(ctx)

    return check_result_repo.save_for_contract.call_args.kwargs["result"]


async def test_payment_percent_validates_amount_by_percent_even_when_some_percents_missing():
    called_result = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="40.00"),
            _make_advance(percent=None, payment_value="60.00"),
        ],
    )

    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, PaymentAmountPercentDiscrepancy) for err in called_result.errors
    )
    assert not any(
        isinstance(err, PaymentPercentSumDiscrepancyCheckResult)
        for err in called_result.errors
    )


async def test_payment_percent_validates_percent_sum_when_all_percents_are_specified():
    called_result = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
        ],
    )

    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, PaymentPercentSumDiscrepancyCheckResult)
        for err in called_result.errors
    )


async def test_payment_percent_succeeds_for_valid_percent_distribution():
    called_result = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_result.status == CheckStatus.success
    assert called_result.errors == []


async def test_payment_percent_succeeds_for_valid_three_payments():
    called_result = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
            _make_advance(percent=Decimal("40.00"), payment_value="40.00"),
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
        ],
    )

    assert called_result.status == CheckStatus.success
    assert called_result.errors == []


async def test_payment_percent_fails_when_amount_does_not_match_percent():
    called_result = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="60.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, PaymentAmountPercentDiscrepancy) for err in called_result.errors
    )


async def test_payment_percent_succeeds_when_percent_sum_difference_within_tolerance():
    called_result = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("49.99"), payment_value="49.99"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_result.status == CheckStatus.success
    assert called_result.errors == []


async def test_payment_percent_succeeds_when_amount_difference_within_tolerance():
    called_result = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="50.01"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_result.status == CheckStatus.success
    assert called_result.errors == []


async def test_payment_percent_fails_when_amount_difference_exceeds_tolerance():
    called_result = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="50.02"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, PaymentAmountPercentDiscrepancy) for err in called_result.errors
    )


async def test_payment_percent_succeeds_when_payment_list_is_empty():
    called_result = await _run_check(total_amount="100.00", advances=[])

    assert called_result.status == CheckStatus.success
    assert called_result.errors == []


async def test_payment_percent_succeeds_for_single_100_percent_payment():
    called_result = await _run_check(
        total_amount="100.00",
        advances=[_make_advance(percent=Decimal("100.00"), payment_value="100.00")],
    )

    assert called_result.status == CheckStatus.success
    assert called_result.errors == []


async def test_payment_percent_can_return_multiple_errors():
    called_result = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="60.00"),
            _make_advance(percent=Decimal("30.00"), payment_value="10.00"),
        ],
    )

    assert called_result.status == CheckStatus.failed
    assert len(called_result.errors) > 1
    assert any(
        isinstance(err, PaymentAmountPercentDiscrepancy) for err in called_result.errors
    )
    assert any(
        isinstance(err, PaymentPercentSumDiscrepancyCheckResult)
        for err in called_result.errors
    )


async def test_payment_percent_sum_checked_when_contract_total_amount_missing():
    called_result = await _run_check(
        total_amount=None,
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_result.status == CheckStatus.success
    assert called_result.errors == []


async def test_payment_percent_sum_fails_when_contract_total_missing_but_percents_not_100():
    called_result = await _run_check(
        total_amount=None,
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
        ],
    )

    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, PaymentPercentSumDiscrepancyCheckResult)
        for err in called_result.errors
    )
    assert not any(
        isinstance(err, PaymentAmountPercentDiscrepancy) for err in called_result.errors
    )
