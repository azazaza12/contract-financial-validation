from dataclasses import dataclass, field
from typing import Any, cast

from app.domain.entities.errors.base import (
    BaseCompareResult,
    BaseContractError,
)
from app.domain.entities.errors.match_result import (
    MatchResult,
    ValueMismatchResult,
)
from app.domain.entities.merge_types import ValueCandidate


@dataclass
class BaseMergeError(BaseContractError):
    kind = "merge"
    field_name: str = ""
    path: str = ""

    def _compare_same_type(self, error: BaseContractError) -> BaseCompareResult:
        other = cast("BaseMergeError", error)
        is_match = (
            self.source == other.source
            and self.field_name == other.field_name
            and self.path == other.path
        )
        if is_match:
            return MatchResult()
        return ValueMismatchResult()


@dataclass
class ValuesDiscrepancyError(BaseMergeError):
    candidates: list[ValueCandidate] = field(default_factory=list)

    def _compare_same_type(self, error: BaseContractError) -> BaseCompareResult:
        other = cast("ValuesDiscrepancyError", error)
        base_result = super()._compare_same_type(error)
        if not base_result.is_match:
            return base_result
        if self.candidates == other.candidates:
            return MatchResult()
        return ValueMismatchResult()


@dataclass
class ValueNotDefinedError(BaseMergeError):
    value: Any = None

    def _compare_same_type(self, error: BaseContractError) -> BaseCompareResult:
        other = cast("ValueNotDefinedError", error)
        base_result = super()._compare_same_type(error)
        if not base_result.is_match:
            return base_result
        if self.value == other.value:
            return MatchResult()
        return ValueMismatchResult()
