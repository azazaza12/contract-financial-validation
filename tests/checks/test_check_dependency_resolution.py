from decimal import Decimal

import pytest

from contract_validation.checks import BaseCheck, Requires
from contract_validation.checks.check_amounts_validation import (
    CheckTotalAmountsValidation,
)
from contract_validation.checks.errors import (
    MissingRequiredFieldError,
    MultiplyRequiredFieldError,
)
from contract_validation.entities import (
    CheckExecutionResult,
    FieldCollector,
    Money,
    Payment,
    PaymentList,
    Source,
    Specification,
    SpecPosition,
    SpecPositionsField,
    TotalAmount,
    TotalAmountField,
    Vat,
    VatInclusion,
)
from tests.conftest import StubDocument, run_check


def _make_total_amount_field(
    value: str,
    document: StubDocument,
) -> TotalAmountField:
    amount = Money(value=Decimal(value), transcription=None)
    total = Payment(
        amount=amount,
        vat=Vat(amount=None, rate=None),
        include_vat=VatInclusion.UNSPECIFIED,
    )
    return TotalAmountField(
        value=TotalAmount(total=total, taxes=PaymentList([])),
        sources=[Source(document_id=document.id)],
    )


def _make_spec_positions_field(
    name: str,
    amount: str,
    document: StubDocument,
) -> SpecPositionsField:
    return SpecPositionsField(
        value=Specification(
            [
                SpecPosition(
                    name=name,
                    quantity=Decimal("1.00"),
                    unit_price=Decimal(amount),
                    total_price=Decimal(amount),
                    unit_of_measurement="шт",
                ),
            ]
        ),
        sources=[Source(document_id=document.id)],
    )


class CheckOneSpecRequires(BaseCheck):
    spec_positions_field = Requires(SpecPositionsField)

    async def execute(self) -> CheckExecutionResult:
        return self._result([])


async def test_optional_dependency_may_be_absent() -> None:
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector([_make_total_amount_field("100.00", document)])
    check = CheckTotalAmountsValidation(tolerance=Decimal("0.01"))

    result = await run_check(check, fields)

    assert result.errors == []


async def test_required_dependency_rejects_several_fields_of_same_type() -> None:
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector(
        [
            _make_spec_positions_field("Позиция А", "100.00", document),
            _make_spec_positions_field("Позиция Б", "200.00", document),
        ],
    )

    with pytest.raises(
        MultiplyRequiredFieldError, match="collision for 'spec_positions_field'"
    ):
        await run_check(CheckOneSpecRequires(), fields)


async def test_required_dependency_rejects_missing_field() -> None:
    document = StubDocument(file_name="doc-1.pdf")
    fields = FieldCollector([_make_total_amount_field("100.00", document)])

    with pytest.raises(
        MissingRequiredFieldError,
        match="missing required field for 'spec_positions_field'",
    ):
        await run_check(CheckOneSpecRequires(), fields)
