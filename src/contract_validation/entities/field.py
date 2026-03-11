from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict
from typing import Iterator
from decimal import Decimal

from app.domain.entities.document import BaseDocument
from app.domain.entities.errors import MergeFieldMessage


@dataclass(kw_only=True, frozen=True)
class BaseField[T](ABC):
    value: T
    document: BaseDocument

    @classmethod
    def solve_collision(cls, fields: list[BaseField]) -> tuple[BaseField, list[MergeFieldMessage]]:
        if not fields:
            raise ValueError(f"{cls.__name__}: empty collision")
        return cls.solve_collision_impl(fields)

    @classmethod
    @abstractmethod
    def solve_collision_impl(cls, fields: list[BaseField]) -> tuple[BaseField, list[MergeFieldMessage]]:
        raise NotImplementedError()


class FieldCollector:
    def __init__(self, fields: list[BaseField]) -> None:
        self._fields: list[BaseField] = fields
        self._type_map: Dict[type[BaseField], list[BaseField]] | None = None

    def extend(self, collector: FieldCollector):
        self._fields.extend(collector._fields)
        self._type_map = None

    def get_type_map(self) -> Dict[type[BaseField], list[BaseField]]:
        if self._type_map is not None:
            return self._type_map

        type_map: Dict[type[BaseField], list[BaseField]] = {}
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
            if len(fields) > 1:
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
