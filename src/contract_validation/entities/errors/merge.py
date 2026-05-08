from dataclasses import dataclass, field
from typing import Any, cast

from app.domain.entities.errors.base import BaseContractError
from app.domain.entities.merge_types import ValueCandidate


@dataclass
class BaseMergeError(BaseContractError):
    kind = "merge"
    field_name: str = ""
    path: str = ""

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("BaseMergeError", error)
        return (
            self.source == other.source
            and self.field_name == other.field_name
            and self.path == other.path
        )


@dataclass
class ValuesDiscrepancyError(BaseMergeError):
    candidates: list[ValueCandidate] = field(default_factory=list)

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("ValuesDiscrepancyError", error)
        base_result = super()._compare_same_type(error)
        if not base_result:
            return base_result
        return self.candidates == other.candidates


@dataclass
class ValueNotDefinedError(BaseMergeError):
    value: Any = None

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("ValueNotDefinedError", error)
        base_result = super()._compare_same_type(error)
        if not base_result:
            return base_result
        return self.value == other.value
