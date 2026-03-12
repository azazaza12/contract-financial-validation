from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, Any
from decimal import Decimal
from dataclasses import is_dataclass, fields as dc_fields, replace

from app.domain.entities.document import BaseDocument
from app.domain.entities.errors import (
    MergeFieldMessage,
    ValuesDiscrepancyMessage,
    ValueNotDefinedMessage,
)


@dataclass(kw_only=True, frozen=True)
class BaseField[T](ABC):
    value: T
    document: BaseDocument
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
    def _compare_values(cls, values: list[Any], path, errors) -> tuple[Any, list[MergeFieldMessage]]:
        defined_values = [v for v in values if v is not None]
        if not defined_values:
            return None, errors
        ref_value = defined_values[0]
        # TODO добавлять ли ошибку ValueNotFountMessage если есть none значения? если да, то только в том случае если есть и не None значения да?
        # TODO не проверять типы
        types = {type(v) for v in defined_values}
        if len(types) > 1:
            # TODO переделать errorsMessage
            errors.append(ValuesDiscrepancyMessage())
            return ref_value, errors

        if is_dataclass(ref_value):
            merged_kwargs = {}
            for f in dc_fields(ref_value):
                attr_vals = [getattr(v, f.name) for v in defined_values]
                merged_attr, errs = cls._compare_values(attr_vals, f"{path}.{f.name}", errors)
                merged_kwargs[f.name] = merged_attr
            return type(ref_value)(**merged_kwargs), errors

        if isinstance(ref_value, list):
            max_length = len(max(defined_values, key=len))
            min_length = len(min(defined_values, key=len))
            # TODO если длина разная, как будто бы хорошо фиксировать какие элементы отсутствуют в других списках
            if max_length != min_length:
                errors.append(ValuesDiscrepancyMessage())
                ##TODO не сравнивать если длина разная
            merged_list = []
            for i in range(max_length):
                item_vals = [v[i] for v in defined_values if i < len(v)]
                merged_item, errs = cls._compare_values(item_vals, f"{path}[{i}]", errors)
                merged_list.append(merged_item)
            return merged_list, errors

        # скаляр
        for v in defined_values[1:]:
            if v != ref_value:
                errors.append(ValuesDiscrepancyMessage())
                return ref_value, errors
        return ref_value, errors

    @classmethod
    def compare_objects(cls, fields: list["BaseField"]) -> tuple[list["BaseField"], list[MergeFieldMessage]]:
        errors: list[MergeFieldMessage] = []
        values = [f.value for f in fields]
        merged_value, errors = cls._compare_values(values=values, path="value", errors=errors)
        if errors:
            incorrect_fields = [replace(f, is_correct = False) for f in fields]
            return incorrect_fields, errors
        #TODO выделять документ(ы?)
        return [cls(value=merged_value, document)], errors


class FieldCollector:
    def __init__(self, fields: list[BaseField]) -> None:
        self._fields: list[BaseField] = fields
        self._type_map: dict[type[BaseField], list[BaseField]] | None = None

    def extend(self, collector: FieldCollector):
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
