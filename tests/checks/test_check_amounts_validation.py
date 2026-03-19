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
    AdvancePayment,
    AdvancePaymentsField,
    Amount,
    Payment,
    SingleSupplierDocument,
    TotalAmountField,
    Vat,
)
from app.domain.entities.validation import CheckStatus
from app.domain.entities.validation_errors import (
    AmountDifferCheckResult,
    AmountNotPositiveCheckResult,
    PaymentSumAndPercentNotFound,
)
from app.domain.pipeline.task import CheckTask
from app.domain.service.checks.check_amounts_validation import (
    CheckTotalAmountsValidation,
)
from tests.domain.pipeline.conftest import create_context


@dataclass(kw_only=True)
class DummyContract(BaseContract):
    def build_pipeline(self, pipeline):
        return pipeline


def _make_payment(value: str, vat_rate: str) -> Payment:
    amount = Amount(value=Decimal(value), transcription=None)
    return Payment(
        amount=amount,
        vat_list=[Vat(amount=amount, rate=Decimal(vat_rate))],
        include_vat=True,
    )


def _run_check(
    *,
    total_amount: str,
    advances: list[AdvancePayment],
):
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    total_amount_field = TotalAmountField(
        value=_make_payment(total_amount, "20.00"),
        sources=[Source(document=document)],
    )
    advance_payments_field = AdvancePaymentsField(
        value=advances,
        sources=[Source(document=document)],
    )
    contract = DummyContract(
        id=uuid4(),
        file_name="contract.pdf",
        documents=[document],
        fields=FieldCollector([total_amount_field, advance_payments_field]),
        errors=[],
    )
    check_result_repo = MagicMock()
    ctx = create_context(contract=contract, check_result_repo=check_result_repo)
    check = CheckTotalAmountsValidation()

    asyncio.run(CheckTask(check=check).run(ctx))

    return check_result_repo.save_for_contract.call_args.kwargs["result"]


def _make_advance(
    *,
    percent: Decimal | None,
    payment_value: str | None,
    vat_rate: str = "20.00",
) -> AdvancePayment:
    payment = _make_payment(payment_value, vat_rate) if payment_value is not None else None
    return AdvancePayment(percent=percent, payment=payment)


def test_check8_succeeds_when_valid_data_with_payments():
    called_result = _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_result.status == CheckStatus.success
    assert called_result.errors == []


def test_check8_succeeds_for_single_payment_sum_not_compared():
    called_result = _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("100.00"), payment_value="10.00"),
        ],
    )

    assert called_result.status == CheckStatus.success
    assert called_result.errors == []


def test_check8_succeeds_when_amount_is_calculated_from_percent():
    called_result = _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value=None),
            _make_advance(percent=Decimal("50.00"), payment_value=None),
        ],
    )

    assert called_result.status == CheckStatus.success
    assert called_result.errors == []


def test_check8_succeeds_when_difference_rounds_to_tolerance():
    called_result = _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="49.989999"),
        ],
    )

    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, AmountDifferCheckResult)
        for err in called_result.errors
    )


def test_check8_fails_on_real_amount_difference():
    called_result = _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="70.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="10.00", vat_rate="10.00"),
        ],
    )

    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, AmountDifferCheckResult) and err.has_different_vats
        for err in called_result.errors
    )


def test_check8_fails_when_tolerance_exceeded():
    called_result = _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="49.97"),
        ],
    )

    assert called_result.status == CheckStatus.failed
    assert any(isinstance(err, AmountDifferCheckResult) for err in called_result.errors)


def test_check8_fails_when_total_amount_not_positive():
    called_result = _run_check(
        total_amount="0.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="0.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="0.00"),
        ],
    )

    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, AmountNotPositiveCheckResult) and err.value == Decimal("0.00")
        for err in called_result.errors
    )


def test_check8_fails_when_payment_amount_not_positive():
    called_result = _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=Decimal("50.00"), payment_value="0.00"),
            _make_advance(percent=Decimal("50.00"), payment_value="100.00"),
        ],
    )

    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, AmountNotPositiveCheckResult) and err.value == Decimal("0.00")
        for err in called_result.errors
    )


def test_check8_fails_when_payment_has_no_amount_and_percent():
    called_result = _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(percent=None, payment_value=None),
            _make_advance(percent=Decimal("100.00"), payment_value="100.00"),
        ],
    )

    assert called_result.status == CheckStatus.failed
    assert any(
        isinstance(err, PaymentSumAndPercentNotFound) and err.index == 1
        for err in called_result.errors
    )


@pytest.mark.parametrize(
    ("advances", "expected_has_different_vats"),
    [
        (
            [
                _make_advance(percent=Decimal("50.00"), payment_value="80.00", vat_rate="20.00"),
                _make_advance(percent=Decimal("50.00"), payment_value="10.00", vat_rate="20.00"),
            ],
            False,
        ),
        (
            [
                _make_advance(percent=Decimal("50.00"), payment_value="80.00", vat_rate="20.00"),
                _make_advance(percent=Decimal("50.00"), payment_value="10.00", vat_rate="10.00"),
            ],
            True,
        ),
    ],
)
def test_check8_sets_has_different_vats_flag(advances, expected_has_different_vats):
    called_result = _run_check(total_amount="100.00", advances=advances)

    assert called_result.status == CheckStatus.failed
    differ_errors = [e for e in called_result.errors if isinstance(e, AmountDifferCheckResult)]
    assert differ_errors
    assert differ_errors[0].has_different_vats == expected_has_different_vats
