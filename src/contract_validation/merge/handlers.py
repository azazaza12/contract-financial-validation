from dataclasses import fields as dc_fields
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities.errors import (
    BaseMergeError,
    ValuesDiscrepancyError,
)
from app.domain.entities.merge_types import Source, ValueCandidate


if TYPE_CHECKING:
    from app.domain.merge.registry import MergeRegistry


def combine_sources(candidates: list[ValueCandidate]) -> list[Source]:
    sources = []
    seen = set()
    for c in candidates:
        for s in c.sources:
            s_id = s.document_id
            if s_id not in seen:
                sources.append(s)
                seen.add(s_id)
    return sources


def all_equal(candidates: list[ValueCandidate]) -> bool:
    if not candidates:
        return True
    first = candidates[0].value
    return all(c.value == first for c in candidates[1:])



def _normalize_str(value: str) -> str:
    return " ".join(value.strip().replace("ё", "е").replace("Ё", "Е").casefold().split())

def all_equal_str(values: list[str]) -> bool:
    if not values:
        return True
    normalized_values = [_normalize_str(value) for value in values]
    first = normalized_values[0]
    return all(n == first for n in normalized_values[1:])


def is_scalar(value_type: type) -> bool:

    return value_type in (
        int,
        float,
        bool,
        Decimal,
        date,
        datetime,
        UUID,
        type(None),
    )


def merge_scalar_strict(
    candidates: list[ValueCandidate],
    path: str,
    errors: list[BaseMergeError],
    _registry: MergeRegistry,
) -> ValueCandidate | None:
    if not all_equal(candidates):
        errors.append(
            ValuesDiscrepancyError(
                candidates=candidates,
                path=path,
            ),
        )
        return None

    return ValueCandidate(
        value=candidates[0].value,
        sources=combine_sources(candidates),
    )


def merge_scalar_strict_str(
    candidates: list[ValueCandidate],
    path: str,
    errors: list[BaseMergeError],
    _registry: MergeRegistry
) -> ValueCandidate | None:
    if not all_equal_str([candidate.value for candidate in candidates]):
        errors.append(ValuesDiscrepancyError(candidates=candidates, path=path))
        return None
    return ValueCandidate(value=candidates[0].value, sources=combine_sources(candidates))


def merge_scalar_pick_first(
    candidates: list[ValueCandidate],
    _path: str,
    _errors: list[BaseMergeError],
    _registry: MergeRegistry,
) -> ValueCandidate | None:
    return ValueCandidate(
        value=candidates[0].value,
        sources=combine_sources(candidates),
    )


def merge_list_strict(
    candidates: list[ValueCandidate],
    path: str,
    errors: list[BaseMergeError],
    registry: MergeRegistry,
) -> ValueCandidate | None:
    lengths = [len(c.value) for c in candidates]

    if len(set(lengths)) > 1:
        errors.append(
            ValuesDiscrepancyError(
                candidates=candidates,
                path=path,
            ),
        )

    max_length = max(lengths)
    merged_list = []

    for i in range(max_length):
        elem_candidates = [
            ValueCandidate(value=c.value[i], sources=c.sources)
            for c in candidates
            if i < len(c.value)
        ]

        merged_elem = registry.merge(elem_candidates, f"{path}[{i}]", errors)
        merged_list.append(merged_elem.value if merged_elem else None)

    return ValueCandidate(
        value=merged_list,
        sources=combine_sources(candidates),
    )


def merge_list_flexible(
    candidates: list[ValueCandidate],
    path: str,
    errors: list[BaseMergeError],
    registry: MergeRegistry,
) -> ValueCandidate | None:
    max_length = max(len(c.value) for c in candidates)
    merged_list = []

    for i in range(max_length):
        elem_candidates = [
            ValueCandidate(value=c.value[i], sources=c.sources)
            for c in candidates
            if i < len(c.value)
        ]

        if elem_candidates:
            merged_elem = registry.merge(elem_candidates, f"{path}[{i}]", errors)
            merged_list.append(merged_elem.value if merged_elem else None)

    return ValueCandidate(
        value=merged_list,
        sources=combine_sources(candidates),
    )


def merge_list_concat(
    candidates: list[ValueCandidate],
    _path: str,
    _errors: list[BaseMergeError],
    _registry: MergeRegistry,
) -> ValueCandidate | None:
    result = []
    for c in candidates:
        result.extend(c.value)

    return ValueCandidate(
        value=result,
        sources=combine_sources(candidates),
    )


def merge_dataclass_default(
    candidates: list[ValueCandidate],
    path: str,
    errors: list[BaseMergeError],
    registry: MergeRegistry,
) -> ValueCandidate | None:
    merged_kwargs = {}

    for field in dc_fields(candidates[0].value):
        field_candidates = [
            ValueCandidate(value=getattr(c.value, field.name), sources=c.sources)
            for c in candidates
        ]

        merged_field = registry.merge(
            field_candidates,
            f"{path}.{field.name}",
            errors,
        )

        merged_kwargs[field.name] = merged_field.value if merged_field else None

    return ValueCandidate(
        value=type(candidates[0].value)(**merged_kwargs),
        sources=combine_sources(candidates),
    )
