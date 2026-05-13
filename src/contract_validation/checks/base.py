from abc import ABC, abstractmethod
from typing import Any, Sequence, Iterable

from app.domain.entities.validation import (
    BaseCheckError,
    CheckExecutionResult,
    CheckStatus,
)
from app.domain.checks.deps import Requires, OptionalDep
from app.domain.entities.field import BaseField


class BaseCheck(ABC):
    @abstractmethod
    async def execute(self, **kwargs: Any) -> CheckExecutionResult:
        raise NotImplementedError

    def prepare(self, fields: Iterable[BaseField]) -> None:
        attr_dict = type(self).__dict__
        for attr_name, declared_type in attr_dict.items():
            if isinstance(declared_type, (Requires, OptionalDep)):
                value = declared_type.resolve(attr_name, fields, self.__class__.__name__)
                setattr(self, attr_name, value)

    def _result(self, errors: list[BaseCheckError]) -> CheckExecutionResult:
        status = CheckStatus.failed if errors else CheckStatus.success
        return CheckExecutionResult(
            label=self.__class__.__name__,
            status=status,
            errors=errors,
        )
