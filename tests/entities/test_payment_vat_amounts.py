from decimal import Decimal

from app.domain.constants import AMOUNT_TOLERANCE
from app.domain.entities import Amount, Basis, Payment, Vat


def _payment(value: str, *, rate: str, include_vat: bool) -> Payment:
    amount = Amount(value=Decimal(value), transcription=None)
    return Payment(
        amount=amount,
        vat=Vat(amount=None, rate=Decimal(rate)),
        include_vat=include_vat,
    )


def test_zero_rate_is_valid_and_computes() -> None:
    payment = _payment("100.00", rate="0", include_vat=True)

    assert payment.expected_vat_amount == Decimal("0.00")
    assert payment.amount_excluding_vat == Decimal("100.00")
    assert payment.amount_including_vat == Decimal("100.00")


def test_rate_minus_hundred_returns_none_instead_of_dividing_by_zero() -> None:
    payment = _payment("120.00", rate="-100", include_vat=True)

    assert payment.expected_vat_amount is None
    assert payment.amount_excluding_vat is None


def test_rate_below_minus_hundred_returns_none() -> None:
    payment = _payment("120.00", rate="-150", include_vat=True)

    assert payment.expected_vat_amount is None
    assert payment.amount_excluding_vat is None


def test_same_footing_rate_minus_hundred_does_not_merge_economically() -> None:
    payment = _payment("120.00", rate="-100", include_vat=True)
    other = _payment("120.00", rate="-100", include_vat=True)

    assert payment.should_merge_economically([other], tolerance=AMOUNT_TOLERANCE) is False


def test_stated_net_keeps_amount_excluding_and_adds_vat_for_including() -> None:
    payment = _payment("100.00", rate="20", include_vat=False)

    assert payment.amount_excluding_vat == Decimal("100.00")
    assert payment.amount_including_vat == Decimal("120.00")


def test_stated_gross_keeps_amount_including_and_strips_vat_for_excluding() -> None:
    payment = _payment("120.00", rate="20", include_vat=True)

    assert payment.amount_including_vat == Decimal("120.00")
    assert payment.amount_excluding_vat == Decimal("100.00")


def test_amount_in_basis_covers_all_three_bases_for_net_payment() -> None:
    payment = _payment("100.00", rate="20", include_vat=False)

    assert payment.amount_in_basis(Basis.INCLUDING_VAT) == Decimal("120.00")
    assert payment.amount_in_basis(Basis.EXCLUDING_VAT) == Decimal("100.00")
    assert payment.amount_in_basis(Basis.RAW) == Decimal("100.00")


def test_amount_in_basis_covers_all_three_bases_for_gross_payment() -> None:
    payment = _payment("120.00", rate="20", include_vat=True)

    assert payment.amount_in_basis(Basis.INCLUDING_VAT) == Decimal("120.00")
    assert payment.amount_in_basis(Basis.EXCLUDING_VAT) == Decimal("100.00")
    assert payment.amount_in_basis(Basis.RAW) == Decimal("120.00")
