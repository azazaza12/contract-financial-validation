from abc import ABC
from dataclasses import dataclass
from typing import Dict
from decimal import Decimal

from app.domain.entities.document import BaseDocument


@dataclass(kw_only=True, frozen=True)
class BaseField[T](ABC):
    value: T
    document: BaseDocument

class FieldCollector:
    def __init__(self, fields: list[BaseField]) -> None:
        self._fields: list[BaseField] = fields
        self._type_map: Dict[type[BaseField], list[BaseField]] | None

    def extend(self, collector: FieldCollector):
        self._fields.extend(collector._fields)

    def get_type_map(self) -> Dict[type[BaseField], list[BaseField]]:
        if self._type_map:
            return self._type_map

        type_map: Dict[type[BaseField], list[BaseField]] = {}
        for field in self._fields:
            if not type_map[type(field)]:
                type_map[type(field)] = []

            type_map[type(field)].append(field)

        self._type_map = type_map
        return self._type_map

    def is_correct(self) -> bool:
        for fields in self.get_type_map().values():
            if len(fields) > 1:
                return False

        return True

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


class DocumentObjectField(BaseField[str]):
    pass


@dataclass(kw_only=True, frozen=True)
class TotalAmountField(BaseField[Decimal]):
    pass


@dataclass(kw_only=True, frozen=True)
class Vat:
    vat_amount: Decimal
    vat_rate: int


@dataclass(kw_only=True, frozen=True)
class AmountWithVat:
    amount: Decimal
    amount_transcription: str
    vat: Vat | None



@dataclass(kw_only=True, frozen=True)
class AdvancePayment:
    percent_payment: int
    amount_with_vat: AmountWithVat | None
    amount_includes_vat: bool


@dataclass(kw_only=True, frozen=True)
class AdvancePaymentsField(BaseField[list[AdvancePayment]]):
    pass


@dataclass(kw_only=True, frozen=True)
class VatBreakdownField(BaseField[list[AmountWithVat]]):
    pass


@dataclass(kw_only=True, frozen=True)
class VatOnlyBreakdownField(BaseField[list[Vat]]):
    pass


@dataclass(kw_only=True, frozen=True)
class SpecPosition:
    name: str
    quantity: float
    unit_price: Decimal
    total_price: Decimal


@dataclass(kw_only=True, frozen=True)
class SpecPositionsField(BaseField[list[str, SpecPosition]]):
    pass

