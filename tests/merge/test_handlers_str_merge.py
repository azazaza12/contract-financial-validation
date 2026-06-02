from uuid import uuid4

import pytest

from app.domain.entities.errors import ValuesDiscrepancyError
from app.domain.entities.merge_types import Source, ValueCandidate
from app.domain.merge.defaults import STRICT_REGISTRY
from app.domain.merge.handlers import (
    all_equal_str,
    merge_scalar_strict_str,
)


def _candidate(value: str) -> ValueCandidate:
    return ValueCandidate(value=value, sources=[Source(document_id=uuid4())])


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["Оборудование", "Оборудование"], True),
        (["  Оборудование  ", "оборудование"], True),
        (["ООО Ромашка", "  ооо   ромашка  "], True),
        (["ёлка", "елка"], True),
        (["Товары", "Услуги"], False),
        (["Оборудование", "Оборудование "], True),
    ],
)
def test_all_equal_str(values: list[str], *, expected: bool) -> None:
    assert all_equal_str(values) is expected


def test_merge_scalar_strict_str_merges_equal_with_different_casing() -> None:
    errors: list = []
    candidates = [_candidate("  Оборудование  "), _candidate("оборудование")]

    result = merge_scalar_strict_str(candidates, "value", errors, STRICT_REGISTRY)

    assert result is not None
    assert result.value == "  Оборудование  "
    assert errors == []
    assert len(result.sources) == len(candidates)


def test_merge_scalar_strict_str_reports_discrepancy() -> None:
    errors: list = []
    candidates = [_candidate("Товары"), _candidate("Услуги")]

    result = merge_scalar_strict_str(candidates, "value", errors, STRICT_REGISTRY)

    assert result is None
    assert len(errors) == 1
    assert isinstance(errors[0], ValuesDiscrepancyError)
    assert errors[0].path == "value"
    assert [c.value for c in errors[0].candidates] == ["Товары", "Услуги"]


def test_strict_registry_routes_str_to_string_handler() -> None:
    doc1, doc2 = uuid4(), uuid4()
    candidates = [
        ValueCandidate(
            value="Один миллион",
            sources=[Source(document_id=doc1)],
        ),
        ValueCandidate(
            value="  один   миллион  ",
            sources=[Source(document_id=doc2)],
        ),
    ]

    result = STRICT_REGISTRY.merge(candidates, "transcription", [])

    assert result is not None
    assert result.value == "Один миллион"
    assert {s.document_id for s in result.sources} == {doc1, doc2}
