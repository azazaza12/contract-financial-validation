from abc import ABC, abstractmethod

from app.domain.entities.validation import (
    BaseCheckError,
    CheckExecutionResult,
    CheckStatus,
)


class BaseCheck(ABC):
    @abstractmethod
    async def execute(self, *args, **kwargs) -> CheckExecutionResult:
        raise NotImplementedError()

    def _result(self, errors: list[BaseCheckError]) -> CheckExecutionResult:
        status = CheckStatus.failed if errors else CheckStatus.success
        return CheckExecutionResult(
            label=self.__class__.__name__,
            status=status,
            errors=errors,
        )
