from decimal import Decimal

from app.domain.entities import Amount, Payment, Vat


def _payment(value: str, *, rate: str, include_vat: bool) -> Payment:
    amount = Amount(value=Decimal(value), transcription=None)
    return Payment(
        amount=amount,
        vat=Vat(amount=None, rate=Decimal(rate)),
        include_vat=include_vat,
    )


def test_zero_rate_is_valid_and_computes() -> None:
    payment = _payment("100.00", rate="0", include_vat=True)

    assert payment.calculated_vat_amount == Decimal("0.00")
    assert payment.amount_excluding_vat == Decimal("100.00")
    assert payment.amount_including_vat == Decimal("100.00")


def test_rate_minus_hundred_returns_none_instead_of_dividing_by_zero() -> None:
    payment = _payment("120.00", rate="-100", include_vat=True)

    assert payment.calculated_vat_amount is None
    assert payment.amount_excluding_vat is None


def test_rate_below_minus_hundred_returns_none() -> None:
    payment = _payment("120.00", rate="-150", include_vat=True)

    assert payment.calculated_vat_amount is None
    assert payment.amount_excluding_vat is None


def test_is_equivalent_to_does_not_crash_on_rate_minus_hundred() -> None:
    payment = _payment("120.00", rate="-100", include_vat=True)
    other = _payment("120.00", rate="-100", include_vat=True)

    assert payment.is_equivalent_to(other) is False
