from decimal import Decimal
from uuid import uuid4

from app.domain.entities import Source, ValueCandidate
from app.domain.entities.errors import ValuesDiscrepancyError
from app.domain.entities.single_supplier_fields import Amount, Payment, Vat
from app.domain.merge import STRICT_REGISTRY
from app.domain.merge.handlers import merge_payment


def _payment(
    *,
    amount: Decimal | None,
    include_vat: bool | None,
    rate: Decimal | None = None,
    vat_amount: Decimal | None = None,
) -> Payment:
    return Payment(
        amount=Amount(value=amount, transcription=None),
        vat=Vat(
            amount=(
                Amount(value=vat_amount, transcription=None)
                if vat_amount is not None
                else None
            ),
            rate=rate,
        ),
        include_vat=include_vat,
    )


def _candidate(payment: Payment) -> ValueCandidate:
    return ValueCandidate(value=payment, sources=[Source(document_id=uuid4())])


def test_is_equivalent_to_true_for_same_net() -> None:
    p1 = _payment(amount=Decimal(100), include_vat=False)
    p2 = _payment(amount=Decimal(100), include_vat=False)
    assert p1.is_equivalent_to(p2) is True


def test_is_equivalent_to_false_for_different_net() -> None:
    p1 = _payment(amount=Decimal(100), include_vat=False)
    p2 = _payment(amount=Decimal(200), include_vat=False)
    assert p1.is_equivalent_to(p2) is False


def test_is_equivalent_to_false_when_net_unavailable() -> None:
    p1 = _payment(amount=Decimal(100), include_vat=None)
    p2 = _payment(amount=Decimal(100), include_vat=None)
    assert p1.is_equivalent_to(p2) is False


def test_merge_payment_assembles_most_complete_when_equivalent() -> None:
    errors: list = []
    complete = _payment(amount=Decimal(100), include_vat=False, rate=Decimal(20))
    partial = _payment(amount=Decimal(100), include_vat=False, rate=None)

    result = merge_payment(
        [_candidate(complete), _candidate(partial)], "total", errors, STRICT_REGISTRY
    )

    assert errors == []
    assert result is not None
    assert result.value.amount_value == Decimal(100)
    assert result.value.vat.rate == Decimal(20)


def test_merge_payment_rate_conflict_reports_targeted_error_and_returns_none() -> None:
    errors: list = []
    p1 = _payment(amount=Decimal(100), include_vat=False, rate=Decimal(20))
    p2 = _payment(amount=Decimal(100), include_vat=False, rate=Decimal(10))

    result = merge_payment(
        [_candidate(p1), _candidate(p2)], "total", errors, STRICT_REGISTRY
    )

    assert result is None
    assert len(errors) == 1
    assert isinstance(errors[0], ValuesDiscrepancyError)
    assert errors[0].path == "total.vat.rate"
    assert {c.value for c in errors[0].candidates} == {Decimal(20), Decimal(10)}


def test_merge_payment_vat_amount_conflict_reports_error_and_returns_none() -> None:
    errors: list = []
    p1 = _payment(
        amount=Decimal(100),
        include_vat=False,
        rate=Decimal(20),
        vat_amount=Decimal(20),
    )
    p2 = _payment(
        amount=Decimal(100),
        include_vat=False,
        rate=Decimal(20),
        vat_amount=Decimal(18),
    )

    result = merge_payment(
        [_candidate(p1), _candidate(p2)], "total", errors, STRICT_REGISTRY
    )

    assert result is None
    assert len(errors) == 1
    assert isinstance(errors[0], ValuesDiscrepancyError)
    assert errors[0].path == "total.vat.amount"


def test_merge_payment_falls_back_to_strict_when_net_differs() -> None:
    errors: list = []
    p1 = _payment(amount=Decimal(100), include_vat=False)
    p2 = _payment(amount=Decimal(200), include_vat=False)

    result = merge_payment(
        [_candidate(p1), _candidate(p2)], "total", errors, STRICT_REGISTRY
    )

    assert any(
        isinstance(e, ValuesDiscrepancyError) and e.path == "total.amount.value"
        for e in errors
    )
    assert result is not None


def test_merge_payment_falls_back_to_strict_when_net_unavailable() -> None:
    errors: list = []
    p1 = _payment(amount=Decimal(100), include_vat=None)
    p2 = _payment(amount=Decimal(100), include_vat=None)

    result = merge_payment(
        [_candidate(p1), _candidate(p2)], "total", errors, STRICT_REGISTRY
    )

    assert errors == []
    assert result is not None
    assert result.value.amount_value == Decimal(100)


def test_is_equivalent_to_true_via_gross_when_net_unavailable() -> None:
    net_stated = _payment(amount=Decimal(100), include_vat=False, rate=Decimal(20))
    gross_without_rate = _payment(amount=Decimal(120), include_vat=True, rate=None)

    assert net_stated.is_equivalent_to(gross_without_rate) is True


def test_merge_payment_assembles_via_gross_when_net_unavailable() -> None:
    errors: list = []
    net_stated = _payment(amount=Decimal(100), include_vat=False, rate=Decimal(20))
    gross_without_rate = _payment(amount=Decimal(120), include_vat=True, rate=None)

    result = merge_payment(
        [_candidate(net_stated), _candidate(gross_without_rate)],
        "total",
        errors,
        STRICT_REGISTRY,
    )

    assert errors == []
    assert result is not None
