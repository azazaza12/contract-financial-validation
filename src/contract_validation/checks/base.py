from abc import ABC, abstractmethod
from typing import Any

from app.domain.entities.validation import (
    BaseResultChecker,
    CheckExecutionResult,
    CheckStatus,
)


class BaseCheck(ABC):
    @abstractmethod
    async def execute(self, **kwargs: Any) -> CheckExecutionResult:
        raise NotImplementedError

    def _result(self, errors: list[BaseResultChecker]) -> CheckExecutionResult:
        status = CheckStatus.failed if errors else CheckStatus.success
        return CheckExecutionResult(
            check_name=self.__class__.__name__,
            status=status,
            errors=errors,
        )
