from collections.abc import Sequence
from dataclasses import fields as dc_fields
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from uuid import UUID

from app.domain.constants import AMOUNT_TOLERANCE
from app.domain.entities.errors.merge import BaseMergeError, ValuesDiscrepancyError
from app.domain.entities.merge_types import Source, SourceHeader, ValueCandidate


if TYPE_CHECKING:
    from app.domain.entities.single_supplier_fields import (
        AdvancePayment,
        Money,
        Payment,
    )

    from .registry import MergeRegistry


def combine_sources(candidates: list[ValueCandidate]) -> list[Source]:
    result: list[Source] = []
    seen: set[tuple[UUID, SourceHeader | None]] = set()
    for c in candidates:
        for s in c.sources:
            key = (s.document_id, s.header)
            if key not in seen:
                seen.add(key)
                result.append(s)
    return result


def all_equal(candidates: list[ValueCandidate]) -> bool:
    if not candidates:
        return True
    first = candidates[0].value
    return all(c.value == first for c in candidates[1:])


def all_equal_decimal(candidates: list[ValueCandidate]) -> bool:
    if not candidates:
        return True
    first = candidates[0].value
    return all(abs(c.value - first) <= AMOUNT_TOLERANCE for c in candidates[1:])


def _normalize_str(value: str) -> str:
    return " ".join(
        value.strip().replace("ё", "е").replace("Ё", "Е").casefold().split()
    )


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
    if isinstance(candidates[0].value, Decimal):
        equal = all_equal_decimal(candidates)
    else:
        equal = all_equal(candidates)
    if not equal:
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
    _registry: MergeRegistry,
) -> ValueCandidate | None:
    if not all_equal_str([candidate.value for candidate in candidates]):
        errors.append(ValuesDiscrepancyError(candidates=candidates, path=path))
        return None
    return ValueCandidate(
        value=candidates[0].value, sources=combine_sources(candidates)
    )


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


def merge_list_skip_empty(
    candidates: list[ValueCandidate],
    path: str,
    errors: list[BaseMergeError],
    registry: MergeRegistry,
) -> ValueCandidate | None:
    non_empty = [c for c in candidates if len(c.value) > 0]

    if not non_empty:
        return ValueCandidate(value=[], sources=combine_sources(candidates))

    if len({len(c.value) for c in non_empty}) > 1:
        errors.append(
            ValuesDiscrepancyError(
                candidates=candidates,
                path=path,
            ),
        )
        return None

    merged_list = []
    for i in range(len(non_empty[0].value)):
        elem_candidates = [
            ValueCandidate(value=c.value[i], sources=c.sources) for c in non_empty
        ]
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


def _assemble_most_complete_payment[T: Payment](payments: list[T]) -> T:
    base = payments[0]

    rate = base.vat.rate
    if rate is None:
        rate = next((p.vat.rate for p in payments if p.vat.rate is not None), None)

    vat_amount = base.vat.amount
    if base.vat.amount_value is None:
        vat_amount = next(
            (p.vat.amount for p in payments if p.vat.amount_value is not None),
            base.vat.amount,
        )

    return replace(base, vat=replace(base.vat, rate=rate, amount=vat_amount))


def _reference_transcription(amounts: list[Money | None]) -> str | None:
    value_bearers = [a for a in amounts if a is not None and a.value is not None]
    transcribed = next((a for a in value_bearers if a.transcription is not None), None)
    if transcribed is not None:
        return transcribed.transcription
    if value_bearers:
        return value_bearers[0].transcription
    present = next((amount for amount in amounts if amount is not None), None)
    return present.transcription if present is not None else None


def _with_reference_transcriptions(
    payment: Payment,
    *,
    amount_transcription: str | None,
    vat_transcription: str | None,
) -> Payment:
    amount = payment.amount
    if amount is not None:
        amount = replace(amount, transcription=amount_transcription)
    vat_amount = payment.vat.amount
    if vat_amount is not None:
        vat_amount = replace(vat_amount, transcription=vat_transcription)
    return replace(payment, amount=amount, vat=replace(payment.vat, amount=vat_amount))


def _harmonize_transcriptions_if_same_footing(
    payments: Sequence[Payment], candidates: list[ValueCandidate]
) -> list[ValueCandidate]:
    if len({payment.include_vat for payment in payments}) != 1:
        return candidates
    amount_transcription = _reference_transcription(
        [payment.amount for payment in payments]
    )
    vat_transcription = _reference_transcription(
        [payment.vat.amount for payment in payments]
    )
    return [
        ValueCandidate(
            value=_with_reference_transcriptions(
                candidate.value,
                amount_transcription=amount_transcription,
                vat_transcription=vat_transcription,
            ),
            sources=candidate.sources,
        )
        for candidate in candidates
    ]


def _vat_conflict(
    payments: Sequence[Payment],
    candidates: list[ValueCandidate],
    path: str,
    errors: list[BaseMergeError],
) -> bool:
    rates = {p.vat.rate for p in payments if p.vat.rate is not None}
    rate_conflict = len(rates) > 1

    vat_amounts = [
        p.vat.amount_value for p in payments if p.vat.amount_value is not None
    ]
    vat_amount_conflict = any(
        abs(a - vat_amounts[0]) > AMOUNT_TOLERANCE for a in vat_amounts[1:]
    )

    if rate_conflict:
        errors.append(
            ValuesDiscrepancyError(
                candidates=[
                    ValueCandidate(value=c.value.vat.rate, sources=c.sources)
                    for c in candidates
                ],
                path=f"{path}.vat.rate",
            )
        )
    if vat_amount_conflict:
        errors.append(
            ValuesDiscrepancyError(
                candidates=[
                    ValueCandidate(value=c.value.vat.amount, sources=c.sources)
                    for c in candidates
                ],
                path=f"{path}.vat.amount",
            )
        )
    return rate_conflict or vat_amount_conflict


def _merge_payment_core[T: Payment](
    values: list[T],
    candidates: list[ValueCandidate],
    path: str,
    errors: list[BaseMergeError],
    registry: MergeRegistry,
) -> T | None:
    if len(candidates) == 1:
        result = merge_dataclass_default(candidates, path, errors, registry)
        return result.value if result else None

    if not values[0].should_merge_economically(values[1:], tolerance=AMOUNT_TOLERANCE):
        harmonized = _harmonize_transcriptions_if_same_footing(values, candidates)
        result = merge_dataclass_default(harmonized, path, errors, registry)
        return result.value if result else None

    if _vat_conflict(values, candidates, path, errors):
        return None

    return _assemble_most_complete_payment(values)


def merge_payment(
    candidates: list[ValueCandidate],
    path: str,
    errors: list[BaseMergeError],
    registry: MergeRegistry,
) -> ValueCandidate | None:
    payments: list[Payment] = [c.value for c in candidates]
    merged = _merge_payment_core(payments, candidates, path, errors, registry)
    if merged is None:
        return None
    return ValueCandidate(value=merged, sources=combine_sources(candidates))


def merge_advance_payment(
    candidates: list[ValueCandidate],
    path: str,
    errors: list[BaseMergeError],
    registry: MergeRegistry,
) -> ValueCandidate | None:
    advances: list[AdvancePayment] = [c.value for c in candidates]
    merged_total = _merge_payment_core(advances, candidates, path, errors, registry)
    if merged_total is None:
        return None

    percent_result = registry.merge(
        [ValueCandidate(value=c.value.percent, sources=c.sources) for c in candidates],
        f"{path}.percent",
        errors,
    )
    payments_result = registry.merge(
        [ValueCandidate(value=c.value.payments, sources=c.sources) for c in candidates],
        f"{path}.payments",
        errors,
    )
    merged = replace(
        merged_total,
        percent=percent_result.value if percent_result else None,
        payments=cast("ValueCandidate", payments_result).value,
    )
    return ValueCandidate(value=merged, sources=combine_sources(candidates))


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
