from abc import ABC
from dataclasses import dataclass

from app.domain.entities.document import BaseDocument


@dataclass
class BaseField(ABC):
    value: str
    document: BaseDocument


@dataclass
class FieldCollector:
    fields: list[BaseField]

    def extend(self, collector: FieldCollector):
        self.fields.extend(collector.fields)

    def __len__(self) -> int:
        return len(self.fields)

    def __bool__(self) -> bool:
        return bool(self.fields)

    def __iter__(self):
        return iter(self.fields)

    def __getitem__(self, index: int) -> BaseField:
        return self.fields[index]

    def __contains__(self, item: BaseField) -> bool:
        return item in self.fields
