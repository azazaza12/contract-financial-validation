from decimal import Decimal
from uuid import uuid4

from app.domain.constants import AMOUNT_TOLERANCE
from app.domain.entities import Source, ValueCandidate
from app.domain.entities.errors import ValuesDiscrepancyError
from app.domain.entities.single_supplier_fields import Money, Payment, Vat, VatInclusion
from app.domain.merge import STRICT_REGISTRY
from app.domain.merge.handlers import merge_payment


def _payment(
    *,
    amount: Decimal | None,
    include_vat: VatInclusion,
    rate: Decimal | None = None,
    vat_amount: Decimal | None = None,
) -> Payment:
    return Payment(
        amount=Money(value=amount, transcription=None),
        vat=Vat(
            amount=(
                Money(value=vat_amount, transcription=None)
                if vat_amount is not None
                else None
            ),
            rate=rate,
        ),
        include_vat=include_vat,
    )


def _candidate(payment: Payment) -> ValueCandidate:
    return ValueCandidate(value=payment, sources=[Source(document_id=uuid4())])


def test_same_footing_does_not_merge_economically() -> None:
    p1 = _payment(amount=Decimal(100), include_vat=VatInclusion.EXCLUDED)
    p2 = _payment(amount=Decimal(100), include_vat=VatInclusion.EXCLUDED)
    assert p1.should_merge_economically([p2], tolerance=AMOUNT_TOLERANCE) is False


def test_unknown_footing_does_not_merge_economically() -> None:
    p1 = _payment(amount=Decimal(100), include_vat=VatInclusion.UNSPECIFIED)
    p2 = _payment(amount=Decimal(100), include_vat=VatInclusion.UNSPECIFIED)
    assert p1.should_merge_economically([p2], tolerance=AMOUNT_TOLERANCE) is False


def test_merges_economically_via_gross_when_net_unavailable() -> None:
    net_stated = _payment(amount=Decimal(100), include_vat=VatInclusion.EXCLUDED, rate=Decimal(20))
    gross_without_rate = _payment(amount=Decimal(120), include_vat=VatInclusion.INCLUDED, rate=None)

    assert (
        net_stated.should_merge_economically(
            [gross_without_rate], tolerance=AMOUNT_TOLERANCE
        )
        is True
    )


def test_does_not_merge_economically_when_converted_amounts_differ() -> None:
    net_stated = _payment(amount=Decimal(100), include_vat=VatInclusion.EXCLUDED, rate=Decimal(20))
    gross_stated = _payment(amount=Decimal(200), include_vat=VatInclusion.INCLUDED, rate=Decimal(20))

    assert (
        net_stated.should_merge_economically([gross_stated], tolerance=AMOUNT_TOLERANCE)
        is False
    )


def test_merge_payment_fills_missing_rate_for_same_footing() -> None:
    errors: list = []
    complete = _payment(amount=Decimal(100), include_vat=VatInclusion.EXCLUDED, rate=Decimal(20))
    partial = _payment(amount=Decimal(100), include_vat=VatInclusion.EXCLUDED, rate=None)

    result = merge_payment(
        [_candidate(complete), _candidate(partial)], "total", errors, STRICT_REGISTRY
    )

    assert errors == []
    assert result is not None
    assert result.value.amount_value == Decimal(100)
    assert result.value.vat.rate == Decimal(20)


def test_merge_payment_assembles_via_gross_when_net_unavailable() -> None:
    errors: list = []
    net_stated = _payment(amount=Decimal(100), include_vat=VatInclusion.EXCLUDED, rate=Decimal(20))
    gross_without_rate = _payment(amount=Decimal(120), include_vat=VatInclusion.INCLUDED, rate=None)

    result = merge_payment(
        [_candidate(net_stated), _candidate(gross_without_rate)],
        "total",
        errors,
        STRICT_REGISTRY,
    )

    assert errors == []
    assert result is not None


def test_merge_payment_same_footing_rate_conflict_reports_field_error() -> None:
    errors: list = []
    p1 = _payment(amount=Decimal(100), include_vat=VatInclusion.EXCLUDED, rate=Decimal(20))
    p2 = _payment(amount=Decimal(100), include_vat=VatInclusion.EXCLUDED, rate=Decimal(10))

    result = merge_payment(
        [_candidate(p1), _candidate(p2)], "total", errors, STRICT_REGISTRY
    )

    assert result is not None
    assert any(
        isinstance(e, ValuesDiscrepancyError) and e.path == "total.vat.rate"
        for e in errors
    )


def test_merge_payment_same_footing_vat_amount_conflict_reports_field_error() -> None:
    errors: list = []
    p1 = _payment(
        amount=Decimal(100),
        include_vat=VatInclusion.EXCLUDED,
        rate=Decimal(20),
        vat_amount=Decimal(20),
    )
    p2 = _payment(
        amount=Decimal(100),
        include_vat=VatInclusion.EXCLUDED,
        rate=Decimal(20),
        vat_amount=Decimal(18),
    )

    result = merge_payment(
        [_candidate(p1), _candidate(p2)], "total", errors, STRICT_REGISTRY
    )

    assert result is not None
    assert any(
        isinstance(e, ValuesDiscrepancyError) and e.path == "total.vat.amount.value"
        for e in errors
    )


def test_merge_payment_flags_same_gross_footing_beyond_tolerance() -> None:
    errors: list = []
    p1 = _payment(amount=Decimal("120.00"), include_vat=VatInclusion.INCLUDED, rate=Decimal(20))
    p2 = _payment(amount=Decimal("121.08"), include_vat=VatInclusion.INCLUDED, rate=Decimal(20))

    result = merge_payment(
        [_candidate(p1), _candidate(p2)], "total", errors, STRICT_REGISTRY
    )

    assert any(
        isinstance(e, ValuesDiscrepancyError) and e.path == "total.amount.value"
        for e in errors
    )
    assert result is not None


def test_merge_payment_falls_back_to_strict_when_amounts_differ() -> None:
    errors: list = []
    p1 = _payment(amount=Decimal(100), include_vat=VatInclusion.EXCLUDED)
    p2 = _payment(amount=Decimal(200), include_vat=VatInclusion.EXCLUDED)

    result = merge_payment(
        [_candidate(p1), _candidate(p2)], "total", errors, STRICT_REGISTRY
    )

    assert any(
        isinstance(e, ValuesDiscrepancyError) and e.path == "total.amount.value"
        for e in errors
    )
    assert result is not None


def test_merge_payment_strict_merges_equal_amounts_when_footing_unknown() -> None:
    errors: list = []
    p1 = _payment(amount=Decimal(100), include_vat=VatInclusion.UNSPECIFIED)
    p2 = _payment(amount=Decimal(100), include_vat=VatInclusion.UNSPECIFIED)

    result = merge_payment(
        [_candidate(p1), _candidate(p2)], "total", errors, STRICT_REGISTRY
    )

    assert errors == []
    assert result is not None
    assert result.value.amount_value == Decimal(100)


def test_merge_payment_pairs_transcription_with_value_bearing_payment() -> None:
    errors: list = []
    words_only = Payment(
        amount=Money(value=None, transcription="сто рублей"),
        vat=Vat(amount=None, rate=None),
        include_vat=VatInclusion.EXCLUDED,
    )
    number_only = Payment(
        amount=Money(value=Decimal(100), transcription=None),
        vat=Vat(amount=None, rate=None),
        include_vat=VatInclusion.EXCLUDED,
    )

    result = merge_payment(
        [_candidate(words_only), _candidate(number_only)],
        "total",
        errors,
        STRICT_REGISTRY,
    )

    assert errors == []
    assert result is not None
    assert result.value.amount.value == Decimal(100)
    assert result.value.amount.transcription is None


def test_merge_payment_keeps_value_bearers_own_transcription() -> None:
    errors: list = []
    stray_words = Payment(
        amount=Money(value=None, transcription="сто"),
        vat=Vat(amount=None, rate=None),
        include_vat=VatInclusion.EXCLUDED,
    )
    full = Payment(
        amount=Money(value=Decimal(100), transcription="сто рублей"),
        vat=Vat(amount=None, rate=None),
        include_vat=VatInclusion.EXCLUDED,
    )

    result = merge_payment(
        [_candidate(stray_words), _candidate(full)],
        "total",
        errors,
        STRICT_REGISTRY,
    )

    assert errors == []
    assert result is not None
    assert result.value.amount.value == Decimal(100)
    assert result.value.amount.transcription == "сто рублей"


def test_merge_payment_keeps_filled_transcription_when_first_bearer_lacks_it() -> None:
    errors: list = []
    number_only = Payment(
        amount=Money(value=Decimal(100000), transcription=None),
        vat=Vat(amount=None, rate=None),
        include_vat=VatInclusion.INCLUDED,
    )
    number_with_words = Payment(
        amount=Money(value=Decimal(100000), transcription="сто тысяч рублей"),
        vat=Vat(amount=None, rate=None),
        include_vat=VatInclusion.INCLUDED,
    )

    result = merge_payment(
        [_candidate(number_only), _candidate(number_with_words)],
        "total",
        errors,
        STRICT_REGISTRY,
    )

    assert errors == []
    assert result is not None
    assert result.value.amount.value == Decimal(100000)
    assert result.value.amount.transcription == "сто тысяч рублей"


def test_group_mixing_shared_and_converted_basis_is_economically_mergeable() -> None:
    shared = _payment(amount=Decimal(120), include_vat=VatInclusion.INCLUDED)
    same_footing = _payment(amount=Decimal(120), include_vat=VatInclusion.INCLUDED)
    converted = _payment(amount=Decimal(100), include_vat=VatInclusion.EXCLUDED, rate=Decimal(20))

    assert (
        shared.should_merge_economically(
            [same_footing, converted], tolerance=AMOUNT_TOLERANCE
        )
        is True
    )


def test_merge_payment_merges_group_mixing_shared_and_converted_basis() -> None:
    errors: list = []
    result = merge_payment(
        [
            _candidate(_payment(amount=Decimal(120), include_vat=VatInclusion.INCLUDED)),
            _candidate(_payment(amount=Decimal(120), include_vat=VatInclusion.INCLUDED)),
            _candidate(
                _payment(amount=Decimal(100), include_vat=VatInclusion.EXCLUDED, rate=Decimal(20))
            ),
        ],
        "total",
        errors,
        STRICT_REGISTRY,
    )

    assert errors == []
    assert result is not None
    assert result.value.amount.value == Decimal(120)
    assert result.value.include_vat is VatInclusion.INCLUDED
    assert result.value.vat.rate == Decimal(20)
