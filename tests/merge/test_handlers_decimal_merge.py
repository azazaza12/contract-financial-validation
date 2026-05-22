from decimal import Decimal
from uuid import uuid4

import pytest
from app.domain.constants import AMOUNT_TOLERANCE
from app.domain.entities.errors import ValuesDiscrepancyError
from app.domain.entities.merge_types import Source, ValueCandidate
from app.domain.merge.defaults import STRICT_REGISTRY
from app.domain.merge.handlers import all_equal_decimal, merge_scalar_strict


def _candidate(value: Decimal) -> ValueCandidate:
    return ValueCandidate(value=value, sources=[Source(document_id=uuid4())])


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([Decimal("100.00"), Decimal("100.00")], True),
        (
            [Decimal("100.00"), Decimal("100.00") + AMOUNT_TOLERANCE - Decimal("0.01")],
            True,
        ),
        (
            [Decimal("100.00"), Decimal("100.00") + AMOUNT_TOLERANCE],
            True,
        ),
        (
            [Decimal("100.00"), Decimal("100.00") + AMOUNT_TOLERANCE + Decimal("0.01")],
            False,
        ),
        ([], True),
    ],
)
def test_all_equal_decimal(values: list[Decimal], *, expected: bool) -> None:
    candidates = [_candidate(v) for v in values]
    assert all_equal_decimal(candidates) is expected


def test_merge_scalar_strict_merges_equal_decimals() -> None:
    errors: list = []
    candidates = [_candidate(Decimal("100.00")), _candidate(Decimal("100.00"))]

    result = merge_scalar_strict(candidates, "amount", errors, STRICT_REGISTRY)

    assert result is not None
    assert result.value == Decimal("100.00")
    assert errors == []
    assert len(result.sources) == len(candidates)


def test_merge_scalar_strict_merges_decimals_within_tolerance() -> None:
    errors: list = []
    within = Decimal("100.00") + AMOUNT_TOLERANCE - Decimal("0.01")
    candidates = [_candidate(Decimal("100.00")), _candidate(within)]

    result = merge_scalar_strict(candidates, "amount", errors, STRICT_REGISTRY)

    assert result is not None
    assert errors == []


def test_merge_scalar_strict_reports_discrepancy_when_decimals_exceed_tolerance() -> None:
    errors: list = []
    exceeds = Decimal("100.00") + AMOUNT_TOLERANCE + Decimal("0.01")
    candidates = [_candidate(Decimal("100.00")), _candidate(exceeds)]

    result = merge_scalar_strict(candidates, "amount", errors, STRICT_REGISTRY)

    assert result is None
    assert len(errors) == 1
    assert isinstance(errors[0], ValuesDiscrepancyError)
    assert errors[0].path == "amount"


def test_strict_registry_routes_decimal_to_decimal_handler() -> None:
    doc1, doc2 = uuid4(), uuid4()
    candidates = [
        ValueCandidate(value=Decimal("100.00"), sources=[Source(document_id=doc1)]),
        ValueCandidate(value=Decimal("100.00"), sources=[Source(document_id=doc2)]),
    ]

    result = STRICT_REGISTRY.merge(candidates, "total_amount", [])

    assert result is not None
    assert result.value == Decimal("100.00")
    assert {s.document_id for s in result.sources} == {doc1, doc2}
