from decimal import Decimal
from uuid import uuid4

from contract_validation.entities import Source, ValueCandidate
from contract_validation.entities.contract_fields import (
    AdvancePayment,
    Money,
    Vat,
    VatInclusion,
)
from contract_validation.entities.errors import ValuesDiscrepancyError
from contract_validation.merge import STRICT_REGISTRY
from contract_validation.merge.handlers import merge_advance_payment


def _advance(
    *,
    amount: Decimal | None,
    include_vat: VatInclusion,
    percent: Decimal | None,
    rate: Decimal | None = None,
) -> AdvancePayment:
    return AdvancePayment(
        percent=percent,
        amount=Money(value=amount, transcription=None),
        vat=Vat(amount=None, rate=rate),
        include_vat=include_vat,
    )


def _candidate(advance: AdvancePayment) -> ValueCandidate:
    return ValueCandidate(value=advance, sources=[Source(document_id=uuid4())])


def test_merge_advance_payment_percent_conflict_reports_single_error() -> None:
    errors: list = []
    a1 = _advance(
        amount=Decimal(100), include_vat=VatInclusion.EXCLUDED, percent=Decimal(30)
    )
    a2 = _advance(
        amount=Decimal(100), include_vat=VatInclusion.EXCLUDED, percent=Decimal(40)
    )

    result = merge_advance_payment(
        [_candidate(a1), _candidate(a2)], "advance", errors, STRICT_REGISTRY
    )

    assert result is not None
    percent_errors = [
        e
        for e in errors
        if isinstance(e, ValuesDiscrepancyError) and e.path == "advance.percent"
    ]
    assert len(percent_errors) == 1


def test_merge_advance_payment_strict_merge_percent_conflict_reports_single_error() -> (
    None
):
    errors: list = []
    complete = _advance(
        amount=Decimal(100),
        include_vat=VatInclusion.EXCLUDED,
        percent=Decimal(30),
        rate=Decimal(20),
    )
    partial = _advance(
        amount=Decimal(100),
        include_vat=VatInclusion.EXCLUDED,
        percent=Decimal(40),
        rate=None,
    )

    result = merge_advance_payment(
        [_candidate(complete), _candidate(partial)], "advance", errors, STRICT_REGISTRY
    )

    assert result is not None
    assert result.value.vat.rate == Decimal(20)
    percent_errors = [
        e
        for e in errors
        if isinstance(e, ValuesDiscrepancyError) and e.path == "advance.percent"
    ]
    assert len(percent_errors) == 1


def test_merge_advance_payment_merges_matching_percent() -> None:
    errors: list = []
    a1 = _advance(
        amount=Decimal(100), include_vat=VatInclusion.EXCLUDED, percent=Decimal(50)
    )
    a2 = _advance(
        amount=Decimal(100), include_vat=VatInclusion.EXCLUDED, percent=Decimal(50)
    )

    result = merge_advance_payment(
        [_candidate(a1), _candidate(a2)], "advance", errors, STRICT_REGISTRY
    )

    assert errors == []
    assert result is not None
    assert result.value.percent == Decimal(50)
    assert result.value.amount_value == Decimal(100)


def test_merge_advance_payment_strict_merge_fills_missing_rate_and_keeps_percent() -> (
    None
):
    errors: list = []
    complete = _advance(
        amount=Decimal(100),
        include_vat=VatInclusion.EXCLUDED,
        percent=Decimal(30),
        rate=Decimal(20),
    )
    partial = _advance(
        amount=Decimal(100),
        include_vat=VatInclusion.EXCLUDED,
        percent=Decimal(30),
        rate=None,
    )

    result = merge_advance_payment(
        [_candidate(complete), _candidate(partial)], "advance", errors, STRICT_REGISTRY
    )

    assert errors == []
    assert result is not None
    assert result.value.amount_value == Decimal(100)
    assert result.value.vat.rate == Decimal(20)
    assert result.value.percent == Decimal(30)


def test_merge_advance_payment_single_candidate_keeps_percent() -> None:
    errors: list = []
    a1 = _advance(
        amount=Decimal(100), include_vat=VatInclusion.EXCLUDED, percent=Decimal(30)
    )

    result = merge_advance_payment([_candidate(a1)], "advance", errors, STRICT_REGISTRY)

    assert errors == []
    assert result is not None
    assert result.value.percent == Decimal(30)
