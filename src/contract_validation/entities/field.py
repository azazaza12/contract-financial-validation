from collections.abc import Hashable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, ClassVar

from app.domain.merge.defaults import DEFAULT_REGISTRY

from .merge_types import Source, ValueCandidate


if TYPE_CHECKING:
    from collections.abc import Iterator

    from app.domain.merge.registry import MergeRegistry

    from .errors.merge import BaseMergeError


@dataclass(kw_only=True, frozen=True)
class BaseField[T]:
    merge_registry: ClassVar[MergeRegistry | None] = None

    value: T
    sources: list[Source]
    is_correct: bool = True

    @classmethod
    def solve_collision(
        cls, fields: list[BaseField]
    ) -> tuple[list[BaseField], list[BaseMergeError]]:
        if not fields:
            msg = f"{cls.__name__}: empty collision"
            raise ValueError(msg)

        registry = (
            cls.merge_registry if cls.merge_registry is not None else DEFAULT_REGISTRY
        )

        errors: list[BaseMergeError] = []
        candidates = [ValueCandidate(value=f.value, sources=f.sources) for f in fields]
        merged = registry.merge(candidates=candidates, path="value", errors=errors)

        if errors:
            incorrect_fields = [replace(f, is_correct=False) for f in fields]
            for error in errors:
                error.field_name = cls.__name__
            return incorrect_fields, errors

        if merged is None:
            incorrect_fields = [replace(f, is_correct=False) for f in fields]
            return incorrect_fields, errors

        return [cls(value=merged.value, sources=merged.sources)], errors

    @property
    def collision_key(self) -> Hashable | None:
        return None


class FieldCollector:
    def __init__(self, fields: list[BaseField]) -> None:
        self._fields: list[BaseField] = fields
        self._type_map: dict[type[BaseField], list[BaseField]] | None = None

    def extend(self, collector: FieldCollector) -> None:
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
            without_key: list[BaseField] = []
            by_key: dict[Hashable, list[BaseField]] = {}

            for field in fields:
                key = field.collision_key
                if key is None:
                    without_key.append(field)
                else:
                    by_key.setdefault(key, []).append(field)
            if len(without_key) > 1:
                yield field_type, without_key

            for grouped_fields in by_key.values():
                if len(grouped_fields) > 1:
                    yield field_type, grouped_fields

    def is_correct(self) -> bool:
        for fields in self.get_type_map().values():
            if not all(field.is_correct for field in fields):
                return False
        return True

    def delete(self, fields: list[BaseField]) -> None:
        for field in fields:
            if field in self._fields:
                self._fields.remove(field)
        self._type_map = None

    def append(self, field: BaseField) -> None:
        self._fields.append(field)
        self._type_map = None

    def __len__(self) -> int:
        return len(self._fields)

    def __bool__(self) -> bool:
        return bool(self._fields)

    def __iter__(self) -> Iterator[BaseField]:
        return iter(self._fields)

    def __getitem__(self, index: int) -> BaseField:
        return self._fields[index]

    def __contains__(self, item: BaseField) -> bool:
        return item in self._fields
