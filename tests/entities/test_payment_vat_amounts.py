from decimal import Decimal

from app.domain.constants import AMOUNT_TOLERANCE
from app.domain.entities import Money, Payment, Vat, VatInclusion


def _payment(value: str, *, rate: str, include_vat: VatInclusion) -> Payment:
    amount = Money(value=Decimal(value), transcription=None)
    return Payment(
        amount=amount,
        vat=Vat(amount=None, rate=Decimal(rate)),
        include_vat=include_vat,
    )


def test_zero_rate_is_valid_and_computes() -> None:
    payment = _payment("100.00", rate="0", include_vat=VatInclusion.INCLUDED)

    assert payment.expected_vat_amount == Decimal("0.00")
    assert payment.amount_excluding_vat == Decimal("100.00")
    assert payment.amount_including_vat == Decimal("100.00")


def test_rate_minus_hundred_returns_none_instead_of_dividing_by_zero() -> None:
    payment = _payment("120.00", rate="-100", include_vat=VatInclusion.INCLUDED)

    assert payment.expected_vat_amount is None
    assert payment.amount_excluding_vat is None


def test_rate_below_minus_hundred_returns_none() -> None:
    payment = _payment("120.00", rate="-150", include_vat=VatInclusion.INCLUDED)

    assert payment.expected_vat_amount is None
    assert payment.amount_excluding_vat is None


def test_same_footing_rate_minus_hundred_does_not_merge_economically() -> None:
    payment = _payment("120.00", rate="-100", include_vat=VatInclusion.INCLUDED)
    other = _payment("120.00", rate="-100", include_vat=VatInclusion.INCLUDED)

    assert (
        payment.should_merge_economically([other], tolerance=AMOUNT_TOLERANCE) is False
    )


def test_stated_net_keeps_amount_excluding_and_adds_vat_for_including() -> None:
    payment = _payment("100.00", rate="20", include_vat=VatInclusion.EXCLUDED)

    assert payment.amount_excluding_vat == Decimal("100.00")
    assert payment.amount_including_vat == Decimal("120.00")


def test_stated_gross_keeps_amount_including_and_strips_vat_for_excluding() -> None:
    payment = _payment("120.00", rate="20", include_vat=VatInclusion.INCLUDED)

    assert payment.amount_including_vat == Decimal("120.00")
    assert payment.amount_excluding_vat == Decimal("100.00")
