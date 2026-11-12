"""Check execution adapter; no dependency on the original contract or pipeline."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from contract_validation.checks.base import BaseCheck
from contract_validation.checks.errors import (
    InsufficientCheckDataError,
    MissingRequiredFieldError,
    MultiplyRequiredFieldError,
)
from contract_validation.entities.errors.base import BaseContractError
from contract_validation.entities.errors.checks import BaseCheckError
from contract_validation.entities.field import FieldCollector
from contract_validation.ports.check_errors import ICheckErrorRepository

from .base import BaseTask, TaskRecord, TaskRuntime, TaskStatus


class CheckContract(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def fields(self) -> FieldCollector: ...

    @property
    def errors(self) -> list[BaseContractError]: ...


class CheckTaskContext(TaskRuntime, Protocol):
    @property
    def contract(self) -> CheckContract: ...

    @property
    def contract_repo(self) -> ICheckErrorRepository: ...


@dataclass(kw_only=True)
class CheckTask(BaseTask[CheckTaskContext]):
    check: BaseCheck

    def create_record(self, status: TaskStatus, error: str | None = None) -> TaskRecord:
        return TaskRecord(
            name=self.__class__.__name__,
            label=self.check.__class__.__name__,
            status=status,
            error_message=error,
        )

    def _should_skip_on_error(self, error: Exception) -> bool:
        return isinstance(
            error,
            (
                InsufficientCheckDataError,
                MultiplyRequiredFieldError,
                MissingRequiredFieldError,
            ),
        )

    async def _run(self, ctx: CheckTaskContext) -> None:
        label = self.check.__class__.__name__
        self.check.prepare(ctx.contract.fields)
        result = await self.check.execute()
        for error in result.errors:
            if isinstance(error, BaseCheckError):
                error.source = label
            ctx.contract.errors.append(error)
        await ctx.contract_repo.save_errors(
            ctx.contract.id, result.errors, kind="check"
        )
