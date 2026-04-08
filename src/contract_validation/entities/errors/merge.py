from dataclasses import dataclass, field
from typing import Any, ClassVar

from app.domain.entities.errors.base import BaseContractError
from app.domain.entities.merge_types import ValueCandidate


@dataclass
class BaseMergeError(BaseContractError):
    _registry: ClassVar[dict[str, type["BaseMergeError"]]] = {}

    kind: ClassVar[str] = "merge"
    field_name: str = ""
    path: str = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        BaseMergeError._registry[cls.__name__] = cls


@dataclass
class ValuesDiscrepancyError(BaseMergeError):
    candidates: list[ValueCandidate] = field(default_factory=list)


@dataclass
class ValueNotDefinedError(BaseMergeError):
    value: Any = None
