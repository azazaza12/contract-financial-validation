from dataclasses import dataclass
from typing import ClassVar, Literal

from app.domain.entities.errors.match_result import (
    BaseCompareResult,
    KindMismatchDetails,
    KindMismatchResult,
    TypeMismatchDetails,
    TypeMismatchResult,
)


@dataclass(kw_only=True)
class BaseContractError:
    kind: ClassVar[Literal["check", "merge"]]
    source: str = ""

    @property
    def error_type(self) -> str:
        return type(self).__name__

    def compare(self, error: BaseContractError) -> BaseCompareResult:
        if type(self) is not type(error):
            return TypeMismatchResult(
                details=TypeMismatchDetails(
                    expected_type=type(self).__name__,
                    actual_type=type(error).__name__,
                )
            )

        if self.kind != error.kind:
            return KindMismatchResult(
                details=KindMismatchDetails(
                    expected_kind=self.kind,
                    actual_kind=error.kind,
                )
            )

        return self._compare_same_type(error)

    def _compare_same_type(self, error: BaseContractError) -> BaseCompareResult:
        msg = f"{type(self).__name__} must implement _compare_same_type"
        raise NotImplementedError(msg)
