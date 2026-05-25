from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence

from app.domain.checks.deps import CheckServices, OptionalDep, Requires
from app.domain.entities.field import BaseField
from app.domain.entities.validation import (
    BaseCheckError,
    CheckExecutionResult,
    CheckStatus,
)


class BaseCheck(ABC):
    @abstractmethod
    async def execute(self, check_services: CheckServices) -> CheckExecutionResult:
        raise NotImplementedError

    def prepare(self, fields: Iterable[BaseField]) -> None:
        attr_dict = type(self).__dict__
        for attr_name, declared_type in attr_dict.items():
            if isinstance(declared_type, (Requires, OptionalDep)):
                value = declared_type.resolve(
                    attr_name, fields, self.__class__.__name__
                )
                setattr(self, attr_name, value)

    def _result(self, errors: Sequence[BaseCheckError]) -> CheckExecutionResult:
        status = CheckStatus.failed if errors else CheckStatus.success
        return CheckExecutionResult(
            label=self.__class__.__name__,
            status=status,
            errors=errors,
        )
