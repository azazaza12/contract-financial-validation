from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from app.domain.checks.check_payment_percent_validation import (
    CheckPaymentPercentValidation,
)
from app.domain.constants import AMOUNT_TOLERANCE
from app.domain.entities import (
    AdvancePayment,
    AdvancePaymentsField,
    Amount,
    FieldCollector,
    Payment,
    Source,
    TotalAmount,
    TotalAmountField,
    Vat,
)
from app.domain.entities.errors import (
    PaymentAmountPercentDiscrepancyError,
    PaymentPercentSumDiscrepancyError,
)
from app.domain.entities.single_supplier import SingleSupplierDocument
from app.domain.entities.validation import CheckStatus
from app.domain.pipeline import TaskStatus
from app.domain.pipeline.task import CheckTask
from tests.domain.pipeline.check_services_stub import STUB_CHECK_SERVICES
from tests.domain.pipeline.conftest import DummyContract, create_context


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
    assert any(
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
            _make_advance(
                percent=Decimal("50.00"),
                payment_value=str(
                    Decimal("50.00") + AMOUNT_TOLERANCE - Decimal("0.01")
                ),
            ),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert called_errors == []


async def test_payment_percent_fails_when_amount_difference_exceeds_tolerance() -> None:
    called_errors = await _run_check(
        total_amount="100.00",
        advances=[
            _make_advance(
                percent=Decimal("50.00"),
                payment_value=str(
                    Decimal("50.00") + AMOUNT_TOLERANCE + Decimal("0.01")
                ),
            ),
            _make_advance(percent=Decimal("50.00"), payment_value="50.00"),
        ],
    )

    assert any(
        isinstance(err, PaymentAmountPercentDiscrepancyError) for err in called_errors
    )


async def test_payment_percent_skips_when_advance_list_is_empty() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    contract = DummyContract(
        id=uuid4(),
        user_id="test-user",
        contract_name="contract.pdf",
        documents=[document],
        fields=FieldCollector(
            [
                TotalAmountField(
                    value=TotalAmount(
                        total=_make_payment("100.00"),
                        taxes=[],
                    ),
                    sources=[Source(document_id=document.id)],
                ),
                AdvancePaymentsField(
                    value=[],
                    sources=[Source(document_id=document.id)],
                ),
            ],
        ),
    )
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(
        check=CheckPaymentPercentValidation(tolerance=AMOUNT_TOLERANCE)
    ).run(
        ctx,
    )

    run = await ctx.pipeline_run_repo.get_by_id(ctx.pipeline.id)
    assert run.records[-1].status == TaskStatus.SKIPPED
    assert "no advance payment records" in (run.records[-1].error_message or "")
    contract_repo.save_errors.assert_not_awaited()


async def test_payment_percent_skips_when_no_advance_has_percent() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    contract = DummyContract(
        id=uuid4(),
        user_id="test-user",
        contract_name="contract.pdf",
        documents=[document],
        fields=FieldCollector(
            [
                TotalAmountField(
                    value=TotalAmount(
                        total=_make_payment("100.00"),
                        taxes=[],
                    ),
                    sources=[Source(document_id=document.id)],
                ),
                AdvancePaymentsField(
                    value=[
                        _make_advance(percent=None, payment_value="50.00"),
                        _make_advance(percent=None, payment_value="50.00"),
                    ],
                    sources=[Source(document_id=document.id)],
                ),
            ],
        ),
    )
    contract_repo = MagicMock()
    ctx = create_context(contract=contract, contract_repo=contract_repo)

    await CheckTask(
        check=CheckPaymentPercentValidation(tolerance=AMOUNT_TOLERANCE)
    ).run(
        ctx,
    )

    run = await ctx.pipeline_run_repo.get_by_id(ctx.pipeline.id)
    assert run.records[-1].status == TaskStatus.SKIPPED
    assert "no advance payment percents" in (run.records[-1].error_message or "")
    contract_repo.save_errors.assert_not_awaited()


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


def _vat_payment(value: str, *, rate: str, include_vat: bool) -> Payment:
    return Payment(
        amount=Amount(value=Decimal(value), transcription=None),
        vat=Vat(amount=None, rate=Decimal(rate)),
        include_vat=include_vat,
    )


async def test_payment_percent_falls_back_to_raw_when_advance_lacks_rate() -> None:
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    total_payment = _vat_payment("100.00", rate="20.00", include_vat=False)
    advances = [
        AdvancePayment(
            percent=Decimal("100.00"),
            total=Payment(
                amount=Amount(value=Decimal("100.00"), transcription=None),
                vat=Vat(amount=None, rate=None),
                include_vat=False,
            ),
            payments=[],
        ),
    ]
    fields = FieldCollector(
        [
            TotalAmountField(
                value=TotalAmount(total=total_payment, taxes=[]),
                sources=[Source(document_id=document.id)],
            ),
            AdvancePaymentsField(
                value=advances,
                sources=[Source(document_id=document.id)],
            ),
        ],
    )
    check = CheckPaymentPercentValidation(tolerance=AMOUNT_TOLERANCE)
    check.prepare(fields)

    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.success
    assert result.errors == []


async def test_payment_percent_uses_advance_payments_for_basis_when_total_has_no_number() -> (  # noqa: E501
    None
):
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    total_payment = _vat_payment("100.00", rate="20.00", include_vat=False)
    numberless_total = Payment(
        amount=None,
        vat=Vat(amount=None, rate=Decimal("20.00")),
        include_vat=False,
    )
    non_grossable_line = Payment(
        amount=Amount(value=Decimal("50.00"), transcription=None),
        vat=Vat(amount=None, rate=None),
        include_vat=False,
    )
    advances = [
        AdvancePayment(
            percent=Decimal("100.00"),
            total=numberless_total,
            payments=[
                _vat_payment("50.00", rate="20.00", include_vat=False),
                non_grossable_line,
            ],
        ),
    ]
    fields = FieldCollector(
        [
            TotalAmountField(
                value=TotalAmount(total=total_payment, taxes=[]),
                sources=[Source(document_id=document.id)],
            ),
            AdvancePaymentsField(
                value=advances,
                sources=[Source(document_id=document.id)],
            ),
        ],
    )
    check = CheckPaymentPercentValidation(tolerance=AMOUNT_TOLERANCE)
    check.prepare(fields)

    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.success
    assert result.errors == []


async def test_payment_percent_basis_ignores_advance_payments_when_total_has_number() -> (  # noqa: E501
    None
):
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    total_payment = _vat_payment("100.00", rate="20.00", include_vat=False)
    advance_total = _vat_payment("120.00", rate="20.00", include_vat=True)
    non_grossable_line = Payment(
        amount=Amount(value=Decimal("77.00"), transcription=None),
        vat=Vat(amount=None, rate=None),
        include_vat=False,
    )
    advances = [
        AdvancePayment(
            percent=Decimal("100.00"),
            total=advance_total,
            payments=[non_grossable_line],
        ),
    ]
    fields = FieldCollector(
        [
            TotalAmountField(
                value=TotalAmount(total=total_payment, taxes=[]),
                sources=[Source(document_id=document.id)],
            ),
            AdvancePaymentsField(
                value=advances,
                sources=[Source(document_id=document.id)],
            ),
        ],
    )
    check = CheckPaymentPercentValidation(tolerance=AMOUNT_TOLERANCE)
    check.prepare(fields)

    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.success
    assert result.errors == []


async def test_payment_percent_succeeds_when_total_net_and_advances_gross_match() -> (
    None
):
    document = SingleSupplierDocument(id=uuid4(), file_name="doc-1.pdf")
    total_payment = _vat_payment("100.00", rate="20.00", include_vat=False)
    advances = [
        AdvancePayment(
            percent=Decimal("50.00"),
            total=_vat_payment("60.00", rate="20.00", include_vat=True),
            payments=[],
        ),
        AdvancePayment(
            percent=Decimal("50.00"),
            total=_vat_payment("60.00", rate="20.00", include_vat=True),
            payments=[],
        ),
    ]
    fields = FieldCollector(
        [
            TotalAmountField(
                value=TotalAmount(total=total_payment, taxes=[]),
                sources=[Source(document_id=document.id)],
            ),
            AdvancePaymentsField(
                value=advances,
                sources=[Source(document_id=document.id)],
            ),
        ],
    )
    check = CheckPaymentPercentValidation(tolerance=AMOUNT_TOLERANCE)
    check.prepare(fields)

    result = await check.execute(STUB_CHECK_SERVICES)

    assert result.status == CheckStatus.success
    assert result.errors == []
