from dataclasses import dataclass, field
from typing import Any

from app.domain.entities.errors.base import BaseContractError
from app.domain.entities.merge_types import ValueCandidate


@dataclass
class BaseMergeError(BaseContractError):
    kind = "merge"
    field_name: str = ""
    path: str = ""


@dataclass
class ValuesDiscrepancyError(BaseMergeError):
    candidates: list[ValueCandidate] = field(default_factory=list)


@dataclass
class ValueNotDefinedError(BaseMergeError):
    value: Any = None
