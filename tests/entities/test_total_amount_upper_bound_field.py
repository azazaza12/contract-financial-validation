from decimal import Decimal

import pytest

from app.domain.entities import (
    AmountOperand,
    Money,
    Payment,
    PaymentList,
    TotalAmount,
    TotalAmountUpperBoundField,
    Vat,
    VatInclusion,
)
from app.domain.entities.errors import UpperBoundAmountError, UpperBoundVatAmountError


def make_payment(
    amount: str | None,
    *,
    vat_amount: str | None = None,
    vat_rate: str | None = None,
    inclusion: VatInclusion = VatInclusion.EXCLUDED,
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


def make_upper_bound_field(bound: Payment) -> TotalAmountUpperBoundField:
    return TotalAmountUpperBoundField(
        value=TotalAmount(total=bound, taxes=PaymentList([])),
        sources=[],
    )


@pytest.mark.parametrize("actual_amount", ["90.00", "100.00", "101.00"])
def test_compare_returns_no_errors_when_amount_is_within_bound_and_tolerance(
    actual_amount: str,
) -> None:
    field = make_upper_bound_field(make_payment("100.00"))

    errors = field.compare(
        make_payment(actual_amount),
        tolerance=Decimal("1.00"),
    )

    assert errors == []


def test_compare_normalizes_amounts_and_preserves_original_operands() -> None:
    field = make_upper_bound_field(
        make_payment(
            "110.00",
            vat_rate="20.00",
            inclusion=VatInclusion.INCLUDED,
        )
    )

    errors = field.compare(
        make_payment(
            "100.00",
            vat_rate="20.00",
            inclusion=VatInclusion.EXCLUDED,
        ),
        tolerance=Decimal("1.00"),
    )

    assert errors == [
        UpperBoundAmountError(
            value=Decimal("120.00"),
            bound_value=Decimal("110.00"),
            violation_value=Decimal("10.00"),
            target_inclusion=VatInclusion.INCLUDED,
            operands=(
                AmountOperand(
                    value=Decimal("100.00"),
                    vat_amount=None,
                    vat_rate=Decimal("20.00"),
                    vat_inclusion=VatInclusion.EXCLUDED,
                ),
            ),
            reference_operand=AmountOperand(
                value=Decimal("110.00"),
                vat_amount=None,
                vat_rate=Decimal("20.00"),
                vat_inclusion=VatInclusion.INCLUDED,
            ),
        )
    ]


def test_compare_checks_vat_amount_when_total_amounts_are_missing() -> None:
    field = make_upper_bound_field(make_payment(None, vat_amount="20.00"))

    errors = field.compare(
        make_payment(None, vat_amount="25.00"),
        tolerance=Decimal("1.00"),
    )

    assert errors == [
        UpperBoundVatAmountError(
            value=Decimal("25.00"),
            bound_value=Decimal("20.00"),
            violation_value=Decimal("5.00"),
        )
    ]


def test_compare_returns_both_errors_when_amount_and_vat_exceed_bounds() -> None:
    field = make_upper_bound_field(make_payment("100.00", vat_amount="20.00"))

    errors = field.compare(
        make_payment("120.00", vat_amount="25.00"),
        tolerance=Decimal("1.00"),
    )

    assert errors == [
        UpperBoundAmountError(
            value=Decimal("120.00"),
            bound_value=Decimal("100.00"),
            violation_value=Decimal("20.00"),
            target_inclusion=VatInclusion.EXCLUDED,
            operands=(
                AmountOperand(
                    value=Decimal("120.00"),
                    vat_amount=Decimal("25.00"),
                    vat_rate=None,
                    vat_inclusion=VatInclusion.EXCLUDED,
                ),
            ),
            reference_operand=AmountOperand(
                value=Decimal("100.00"),
                vat_amount=Decimal("20.00"),
                vat_rate=None,
                vat_inclusion=VatInclusion.EXCLUDED,
            ),
        ),
        UpperBoundVatAmountError(
            value=Decimal("25.00"),
            bound_value=Decimal("20.00"),
            violation_value=Decimal("5.00"),
        ),
    ]
