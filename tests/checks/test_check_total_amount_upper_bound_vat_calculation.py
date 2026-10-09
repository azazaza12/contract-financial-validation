from decimal import Decimal

import pytest

from contract_validation.checks.check_vat_calculation import (
    CheckTotalAmountUpperBoundVatCalculation,
)
from contract_validation.checks.errors import InsufficientCheckDataError
from contract_validation.constants import AMOUNT_TOLERANCE
from contract_validation.entities import (
    Money,
    Payment,
    PaymentList,
    TotalAmount,
    TotalAmountUpperBoundField,
    Vat,
    VatInclusion,
)
from contract_validation.entities.errors import VatAmountCalculationDiscrepancyError
from contract_validation.entities.validation import CheckStatus


pytestmark = pytest.mark.asyncio


def make_payment(
    *,
    amount: str | None,
    vat_amount: str | None,
    vat_rate: str | None,
    inclusion: VatInclusion = VatInclusion.INCLUDED,
) -> Payment:
    return Payment(
        amount=(
            Money(value=Decimal(amount), transcription=None)
            if amount is not None
            else None
        ),
        vat=Vat(
            amount=(
                Money(value=Decimal(vat_amount), transcription=None)
                if vat_amount is not None
                else None
            ),
            rate=Decimal(vat_rate) if vat_rate is not None else None,
        ),
        include_vat=inclusion,
    )


async def run_check(
    total: Payment,
    *,
    taxes: list[Payment] | None = None,
):
    check = CheckTotalAmountUpperBoundVatCalculation(tolerance=AMOUNT_TOLERANCE)
    check.upper_bound_amount_field = TotalAmountUpperBoundField(
        value=TotalAmount(
            total=total,
            taxes=PaymentList(taxes or []),
        ),
        sources=[],
    )
    return await check.execute()


async def test_upper_bound_vat_calculation_succeeds_when_formula_is_correct() -> None:
    result = await run_check(
        make_payment(amount="120.00", vat_amount="20.00", vat_rate="20.00")
    )

    assert result.status is CheckStatus.SUCCESS
    assert result.errors == []


async def test_upper_bound_vat_calculation_reports_incorrect_formula() -> None:
    result = await run_check(
        make_payment(amount="120.00", vat_amount="22.00", vat_rate="20.00")
    )

    assert result.status is CheckStatus.FAILED
    assert result.errors == [
        VatAmountCalculationDiscrepancyError(
            amount=Decimal("120.00"),
            rate=Decimal("20.00"),
            include_vat=True,
            expected_vat_amount=Decimal("20.00"),
            vat_amount=Decimal("22.00"),
            difference=Decimal("2.00"),
        )
    ]


async def test_upper_bound_vat_calculation_verifies_taxes() -> None:
    result = await run_check(
        make_payment(amount=None, vat_amount=None, vat_rate=None),
        taxes=[make_payment(amount="120.00", vat_amount="22.00", vat_rate="20.00")],
    )

    assert result.status is CheckStatus.FAILED
    assert len(result.errors) == 1
    assert isinstance(result.errors[0], VatAmountCalculationDiscrepancyError)


async def test_upper_bound_vat_calculation_skips_without_required_data() -> None:
    check = CheckTotalAmountUpperBoundVatCalculation(tolerance=AMOUNT_TOLERANCE)
    check.upper_bound_amount_field = TotalAmountUpperBoundField(
        value=TotalAmount(
            total=make_payment(amount="120.00", vat_amount=None, vat_rate=None),
            taxes=PaymentList([]),
        ),
        sources=[],
    )

    with pytest.raises(InsufficientCheckDataError):
        await check.execute()
