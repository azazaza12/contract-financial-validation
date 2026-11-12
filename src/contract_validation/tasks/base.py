"""Minimal task lifecycle adapted from the shared application pipeline."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SKIPPED = "skipped"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(kw_only=True, frozen=True)
class TaskRecord:
    name: str
    label: str | None = None
    status: TaskStatus
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    error_message: str | None = None


class TaskRuntime(Protocol):
    async def add_record(self, record: TaskRecord) -> None: ...


@dataclass(kw_only=True)
class BaseTask[TCtx: TaskRuntime](ABC):
    label: str | None = None

    def create_record(self, status: TaskStatus, error: str | None = None) -> TaskRecord:
        return TaskRecord(
            name=self.__class__.__name__,
            label=self.label,
            status=status,
            error_message=error,
        )

    async def run(self, ctx: TCtx) -> None:
        try:
            await ctx.add_record(self.create_record(TaskStatus.RUNNING))
            await self._run(ctx)
            await ctx.add_record(self.create_record(TaskStatus.SUCCESS))
        except Exception as error:
            if self._should_skip_on_error(error):
                await ctx.add_record(
                    self.create_record(TaskStatus.SKIPPED, error=str(error))
                )
                return
            await ctx.add_record(
                self.create_record(TaskStatus.FAILED, error=str(error))
            )
            raise

    def _should_skip_on_error(self, _error: Exception) -> bool:
        return False

    @abstractmethod
    async def _run(self, ctx: TCtx) -> None: ...
