from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.domain.checks.check_payment_percent_validation import (
    CheckPaymentPercentValidation,
)
from app.domain.entities.errors import (
    PaymentAmountPercentDiscrepancyError,
    PaymentPercentSumDiscrepancyError,
)
from app.domain.entities.field import FieldCollector
from app.domain.entities.merge_types import Source
from app.domain.entities.single_supplier import SingleSupplierDocument
from app.domain.entities.single_supplier_fields import (
    AdvancePayment,
    AdvancePaymentsField,
    Amount,
    Payment,
    TotalAmount,
    TotalAmountField,
    Vat,
)
from app.domain.pipeline.task import CheckTask

from tests.domain.pipeline.conftest import DummyContract, create_context


from app.domain.constants import AMOUNT_TOLERANCE

pytestmark = pytest.mark.asyncio


def _make_payment(value: str, vat_rate: str = "20.00") -> Payment:
    amount = Amount(value=Decimal(value), transcription=None)
    return Payment(
        amount=amount,
        vat=Vat(amount=amount, rate=Decimal(vat_rate)),
        include_vat=True,
    )


def _make_advance(
    *,
    percent: Decimal | None,
    payment_value: str | None,
) -> AdvancePayment:
    total = _make_payment(payment_value) if payment_value is not None else None
    return AdvancePayment(percent=percent, total=total, payments=[])


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
            taxes=[],
        ),
        sources=[Source(document_id=document.id)],
    )
    advance_payments_field = AdvancePaymentsField(
        value=advances,
        sources=[Source(document_id=document.id)],
    )
    contract = DummyContract(
        id=uuid4(),
        user_id="test-user",
        contract_name="contract.pdf",
        documents=[document],
        fields=FieldCollector([total_amount_field, advance_payments_field]),
    )
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)
    check = CheckPaymentPercentValidation(tolerance=AMOUNT_TOLERANCE)

    await CheckTask(check=check).run(ctx)

    return contract_repo.save_errors.call_args.args[1]


async def test_payment_percent_validates_amount_even_when_percents_missing() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="40.00"),
            _make_advance(percent=None, payment_value="60.00"),
        ],
    )

    assert any(
        isinstance(err, PaymentAmountPercentDiscrepancyError) for err in called_errors
    )
    assert not any(
        isinstance(err, PaymentPercentSumDiscrepancyError) for err in called_errors
    )


async def test_payment_percent_validates_percent_sum_when_all_percents_are_specified() -> (  # noqa: E501
    None
):
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
        ],
    )

    assert any(
        isinstance(err, PaymentPercentSumDiscrepancyError) for err in called_errors
    )


async def test_payment_percent_succeeds_for_valid_percent_distribution() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_errors == []


async def test_payment_percent_succeeds_for_valid_three_payments() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
            _make_advance(percent=Decimal("40.00"), payment_value="40.00"),
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
        ],
    )

    assert called_errors == []


async def test_payment_percent_fails_when_amount_does_not_match_percent() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="60.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert any(
        isinstance(err, PaymentAmountPercentDiscrepancyError) for err in called_errors
    )


async def test_payment_percent_succeeds_when_percent_sum_difference_within_tolerance() -> (  # noqa: E501
    None
):
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("49.99"), payment_value="49.99"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_errors == []


async def test_payment_percent_succeeds_when_amount_difference_within_tolerance() -> (
    None
):
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value=str(Decimal("50.00") + AMOUNT_TOLERANCE - Decimal("0.01"))),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_errors == []


async def test_payment_percent_fails_when_amount_difference_exceeds_tolerance() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value=str(Decimal("50.00") + AMOUNT_TOLERANCE + Decimal("0.01"))),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert any(
        isinstance(err, PaymentAmountPercentDiscrepancyError) for err in called_errors
    )


async def test_payment_percent_succeeds_when_payment_list_is_empty() -> None:
    called_errors = await _run_check(total_amount="100.00", advances=[])

    assert called_errors == []


async def test_payment_percent_succeeds_for_single_100_percent_payment() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[_make_advance(percent=Decimal("100.00"), payment_value="100.00")],
    )

    assert called_errors == []


async def test_payment_percent_can_return_multiple_errors() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="60.00"),
            _make_advance(percent=Decimal("30.00"), payment_value="10.00"),
        ],
    )

    assert len(called_errors) > 1
    assert any(
        isinstance(err, PaymentAmountPercentDiscrepancyError) for err in called_errors
    )
    assert any(
        isinstance(err, PaymentPercentSumDiscrepancyError) for err in called_errors
    )


async def test_payment_percent_sum_checked_when_contract_total_amount_missing() -> None:
    called_errors = await _run_check(
        total_amount=None,
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_errors == []


async def test_payment_percent_sum_fails_without_total_when_not_100() -> None:
    called_errors = await _run_check(
        total_amount=None,
        advances=[
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
            _make_advance(percent=Decimal("30.00"), payment_value="30.00"),
        ],
    )

    assert any(
        isinstance(err, PaymentPercentSumDiscrepancyError) for err in called_errors
    )
    assert not any(
        isinstance(err, PaymentAmountPercentDiscrepancyError) for err in called_errors
    )
