from abc import ABC, abstractmethod
from dataclasses import dataclass, is_dataclass, replace
from dataclasses import fields as dc_fields
from typing import Iterator

from app.domain.entities.errors import (
    MergeFieldMessage,
    ValuesDiscrepancyMessage,
)
from app.domain.entities.merge_types import Source, ValueCandidate


@dataclass(kw_only=True, frozen=True)
class BaseField[T](ABC):
    value: T
    sources: list[Source]
    is_correct: bool = True

    @classmethod
    def solve_collision(
        cls, fields: list["BaseField"]
    ) -> tuple[list["BaseField"], list[MergeFieldMessage]]:
        if not fields:
            raise ValueError(f"{cls.__name__}: empty collision")
        return cls.solve_collision_impl(fields)

    @classmethod
    @abstractmethod
    def solve_collision_impl(
        cls, fields: list["BaseField"]
    ) -> tuple[list["BaseField"], list[MergeFieldMessage]]:
        raise NotImplementedError()

    @classmethod
    def _compare_values(
        cls,
        candidates: list[ValueCandidate],
        path: str,
        errors: list[MergeFieldMessage],
    ) -> ValueCandidate | None:

        defined_candidates = [c for c in candidates if c.value is not None]
        defined_values = [c.value for c in defined_candidates]
        sources = [s for c in candidates for s in c.sources]
        if not defined_candidates:
            return ValueCandidate(value=None, sources=sources)
        ref_candidate = defined_candidates[0]

        if is_dataclass(ref_candidate.value):
            merged_kwargs = {}
            for f in dc_fields(ref_candidate.value):
                attr_candidates = [
                    ValueCandidate(value=getattr(c.value, f.name), sources=c.sources)
                    for c in defined_candidates
                ]
                merged_candidate = cls._compare_values(
                    attr_candidates, f"{path}.{f.name}", errors
                )
                if merged_candidate is None:
                    merged_kwargs[f.name] = None
                else:
                    merged_kwargs[f.name] = merged_candidate.value
            return ValueCandidate(
                value=type(ref_candidate.value)(**merged_kwargs),
                sources=sources,
            )

        if isinstance(ref_candidate.value, list):
            max_length = len(max(defined_values, key=len))
            min_length = len(min(defined_values, key=len))
            if max_length != min_length:
                errors.append(
                    ValuesDiscrepancyMessage(
                        candidates=candidates,
                        path=path,
                        field_type=cls,
                    )
                )
                return None
            else:
                merged_list = []
                for i in range(max_length):
                    nested_candidates = [
                        ValueCandidate(value=c.value[i], sources=c.sources)
                        for c in defined_candidates
                        if i < len(c.value)
                    ]
                    merged_candidate = cls._compare_values(
                        nested_candidates, f"{path}[{i}]", errors
                    )
                    merged_list.append(
                        merged_candidate.value if merged_candidate is not None else None
                    )
                return ValueCandidate(value=merged_list, sources=sources)

        # скаляр
        for c in defined_candidates[1:]:
            if c.value != ref_candidate.value:
                errors.append(
                    ValuesDiscrepancyMessage(
                        candidates=candidates,
                        field_type=cls,
                        path=path,
                    )
                )
                return None
        return ValueCandidate(value=ref_candidate.value, sources=sources)

    @classmethod
    def compare_objects(
        cls, fields: list["BaseField"]
    ) -> tuple[list["BaseField"], list[MergeFieldMessage]]:
        errors: list[MergeFieldMessage] = []
        candidates = [ValueCandidate(value=f.value, sources=f.sources) for f in fields]
        merged_candidate = cls._compare_values(
            candidates=candidates, path="value", errors=errors
        )
        if errors or merged_candidate is None:
            incorrect_fields = [replace(f, is_correct=False) for f in fields]
            return incorrect_fields, errors
        return [
            cls(value=merged_candidate.value, sources=merged_candidate.sources)
        ], errors


class FieldCollector:
    def __init__(self, fields: list[BaseField]) -> None:
        self._fields: list[BaseField] = fields
        self._type_map: dict[type[BaseField], list[BaseField]] | None = None

    def extend(self, collector: "FieldCollector"):
        self._fields.extend(collector._fields)
        self._type_map = None

    def get_type_map(self) -> dict[type[BaseField], list[BaseField]]:
        if self._type_map is not None:
            return self._type_map

        type_map: dict[type[BaseField], list[BaseField]] = {}
        for field in self._fields:
            field_type = type(field)
            if field_type not in type_map:
                type_map[field_type] = []
            type_map[field_type].append(field)

        self._type_map = type_map
        return self._type_map

    def get_next_collision(self) -> Iterator[tuple[type[BaseField], list[BaseField]]]:
        for field_type, fields in self.get_type_map().items():
            if len(fields) > 1:
                yield field_type, fields

    def is_correct(self) -> bool:
        for fields in self.get_type_map().values():
            if not all(field.is_correct for field in fields):
                return False
        return True

    def delete(self, fields):
        for field in fields:
            if field in self._fields:
                self._fields.remove(field)
        self._type_map = None

    def append(self, field):
        self._fields.append(field)
        self._type_map = None

    def __len__(self) -> int:
        return len(self._fields)

    def __bool__(self) -> bool:
        return bool(self._fields)

    def __iter__(self):
        return iter(self._fields)

    def __getitem__(self, index: int) -> BaseField:
        return self._fields[index]

    def __contains__(self, item: BaseField) -> bool:
        return item in self._fields
