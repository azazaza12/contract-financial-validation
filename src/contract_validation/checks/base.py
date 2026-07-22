from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.domain.entities.validation import CheckExecutionResult, CheckStatus

from .deps import OptionalDep, Requires


if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from app.domain.entities.errors.checks import BaseCheckError
    from app.domain.entities.field import BaseField


class BaseCheck(ABC):
    @abstractmethod
    async def execute(self) -> CheckExecutionResult: ...

    def prepare(self, fields: Iterable[BaseField]) -> None:
        attr_dict = type(self).__dict__
        for attr_name, declared_type in attr_dict.items():
            if isinstance(declared_type, (Requires, OptionalDep)):
                value = declared_type.resolve(
                    attr_name, fields, self.__class__.__name__
                )
                setattr(self, attr_name, value)

    def _result(self, errors: Sequence[BaseCheckError]) -> CheckExecutionResult:
        status = CheckStatus.FAILED if errors else CheckStatus.SUCCESS
        return CheckExecutionResult(
            label=self.__class__.__name__,
            status=status,
            errors=errors,
        )
