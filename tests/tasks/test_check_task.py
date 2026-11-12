from asyncio import CancelledError
from collections.abc import Sequence
from dataclasses import FrozenInstanceError, dataclass, field
from datetime import UTC
from typing import cast
from uuid import UUID, uuid4

import pytest

from contract_validation.checks import BaseCheck, OptionalDep, Requires
from contract_validation.checks.check_values_validation import CheckValuesValidation
from contract_validation.checks.errors import (
    CheckInputError,
    InsufficientCheckDataError,
    InvalidCheckSignatureError,
)
from contract_validation.entities import CheckExecutionResult, FieldCollector
from contract_validation.entities.errors.base import BaseContractError
from contract_validation.entities.errors.checks import (
    AmountNotFoundError,
    BaseCheckError,
    PaymentVatRateNotFoundError,
)
from contract_validation.entities.field import BaseField
from contract_validation.tasks import (
    BaseTask,
    CheckTask,
    CheckTaskContext,
    TaskRecord,
    TaskRuntime,
    TaskStatus,
)


class InputField(BaseField[str]):
    pass


class OtherField(BaseField[str]):
    pass


@dataclass
class StubContract:
    fields: FieldCollector = field(default_factory=lambda: FieldCollector([]))
    id: UUID = field(default_factory=uuid4)
    errors: list[BaseContractError] = field(default_factory=list)


@dataclass
class MemoryErrorRepository:
    saved: list[tuple[UUID, list[BaseContractError], str]] = field(default_factory=list)
    failure: Exception | None = None

    async def save_errors(
        self, contract_id: UUID, errors: Sequence[BaseContractError], kind: str
    ) -> None:
        if self.failure is not None:
            raise self.failure
        self.saved.append((contract_id, list(errors), kind))


@dataclass
class MemoryContext:
    contract: StubContract = field(default_factory=StubContract)
    contract_repo: MemoryErrorRepository = field(default_factory=MemoryErrorRepository)
    records: list[TaskRecord] = field(default_factory=list)
    fail_success_record: bool = False

    async def add_record(self, record: TaskRecord) -> None:
        if self.fail_success_record and record.status is TaskStatus.SUCCESS:
            raise RuntimeError("record storage unavailable")
        self.records.append(record)


class RecordingCheck(BaseCheck):
    input_field = Requires(InputField)

    def __init__(
        self,
        *,
        errors: Sequence[BaseCheckError] = (),
        failure: BaseException | None = None,
    ) -> None:
        self.errors = errors
        self.failure = failure
        self.executed = False
        self.received: InputField | None = None

    async def execute(self) -> CheckExecutionResult:
        self.executed = True
        self.received = cast("InputField", self.input_field)
        if self.failure is not None:
            raise self.failure
        return self._result(self.errors)


class OptionalCheck(BaseCheck):
    input_field = OptionalDep(InputField)

    def __init__(self) -> None:
        self.executed = False

    async def execute(self) -> CheckExecutionResult:
        self.executed = True
        return self._result([])


def make_context(*, input_count: int = 1) -> MemoryContext:
    return MemoryContext(
        contract=StubContract(
            fields=FieldCollector(
                [InputField(value=str(i), sources=[]) for i in range(input_count)]
            )
        )
    )


def statuses(ctx: MemoryContext) -> list[TaskStatus]:
    return [record.status for record in ctx.records]


async def test_task_prepares_fields_before_execution_and_saves_empty_result() -> None:
    ctx = make_context()
    expected_field = ctx.contract.fields[0]
    ctx.contract.fields.append(OtherField(value="unrelated", sources=[]))
    check = RecordingCheck()
    task = CheckTask(check=check)

    await task.run(ctx)

    assert check.executed
    assert check.received is expected_field
    assert ctx.contract.errors == []
    assert ctx.contract_repo.saved == [(ctx.contract.id, [], "check")]
    assert statuses(ctx) == [TaskStatus.RUNNING, TaskStatus.SUCCESS]
    assert all(record.name == "CheckTask" for record in ctx.records)
    assert all(record.label == "RecordingCheck" for record in ctx.records)
    assert all(record.error_message is None for record in ctx.records)


async def test_all_discrepancies_are_saved_without_failing_task() -> None:
    ctx = make_context()
    previous_error = AmountNotFoundError(source="earlier-check")
    ctx.contract.errors.append(previous_error)
    errors = (AmountNotFoundError(), PaymentVatRateNotFoundError())

    await CheckTask(check=RecordingCheck(errors=errors)).run(ctx)

    assert ctx.contract.errors == [previous_error, *errors]
    assert previous_error.source == "earlier-check"
    assert all(error.source == "RecordingCheck" for error in errors)
    assert ctx.contract_repo.saved == [(ctx.contract.id, list(errors), "check")]
    assert statuses(ctx) == [TaskStatus.RUNNING, TaskStatus.SUCCESS]


@pytest.mark.parametrize("input_count", [0, 2])
async def test_missing_or_ambiguous_required_field_skips_execution(
    input_count: int,
) -> None:
    ctx = make_context(input_count=input_count)
    check = RecordingCheck()

    await CheckTask(check=check).run(ctx)

    assert not check.executed
    assert ctx.contract.errors == []
    assert ctx.contract_repo.saved == []
    assert statuses(ctx) == [TaskStatus.RUNNING, TaskStatus.SKIPPED]
    assert "input_field" in (ctx.records[-1].error_message or "")


async def test_absent_optional_field_does_not_skip_check() -> None:
    ctx = make_context(input_count=0)
    check = OptionalCheck()

    await CheckTask(check=check).run(ctx)

    assert check.executed
    assert check.input_field is None
    assert statuses(ctx) == [TaskStatus.RUNNING, TaskStatus.SUCCESS]
    assert ctx.contract_repo.saved == [(ctx.contract.id, [], "check")]


async def test_ambiguous_optional_field_skips_check() -> None:
    ctx = make_context(input_count=2)
    check = OptionalCheck()

    await CheckTask(check=check).run(ctx)

    assert not check.executed
    assert statuses(ctx) == [TaskStatus.RUNNING, TaskStatus.SKIPPED]
    assert ctx.contract_repo.saved == []


async def test_insufficient_data_during_execution_skips_check() -> None:
    ctx = make_context()
    error = InsufficientCheckDataError("RecordingCheck", "no comparable amounts")
    check = RecordingCheck(failure=error)

    await CheckTask(check=check).run(ctx)

    assert check.executed
    assert statuses(ctx) == [TaskStatus.RUNNING, TaskStatus.SKIPPED]
    assert ctx.records[-1].error_message == str(error)
    assert ctx.contract_repo.saved == []
    assert ctx.contract.errors == []


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("calculation failed"),
        InvalidCheckSignatureError("invalid signature"),
        CheckInputError("not one of the explicitly skippable errors"),
    ],
)
async def test_unexpected_error_is_recorded_and_reraised(error: Exception) -> None:
    ctx = make_context()

    with pytest.raises(type(error)) as caught:
        await CheckTask(check=RecordingCheck(failure=error)).run(ctx)

    assert caught.value is error
    assert statuses(ctx) == [TaskStatus.RUNNING, TaskStatus.FAILED]
    assert ctx.records[-1].error_message == str(error)
    assert ctx.contract_repo.saved == []
    assert ctx.contract.errors == []


async def test_save_failure_propagates_without_rolling_back_in_memory() -> None:
    ctx = make_context()
    error = AmountNotFoundError()
    failure = RuntimeError("error storage unavailable")
    ctx.contract_repo.failure = failure

    with pytest.raises(RuntimeError, match="error storage unavailable") as caught:
        await CheckTask(check=RecordingCheck(errors=[error])).run(ctx)

    assert caught.value is failure
    assert statuses(ctx) == [TaskStatus.RUNNING, TaskStatus.FAILED]
    assert ctx.contract_repo.saved == []
    # The original adapter appends before saving; transaction/rollback is external.
    assert ctx.contract.errors == [error]


async def test_record_failure_after_save_propagates_without_undoing_save() -> None:
    ctx = make_context()
    ctx.fail_success_record = True

    with pytest.raises(RuntimeError, match="record storage unavailable"):
        await CheckTask(check=RecordingCheck()).run(ctx)

    assert ctx.contract_repo.saved == [(ctx.contract.id, [], "check")]
    assert statuses(ctx) == [TaskStatus.RUNNING, TaskStatus.FAILED]


async def test_real_financial_check_saves_discrepancy_and_allows_next_task() -> None:
    ctx = make_context()
    next_check = RecordingCheck()

    await CheckTask(check=CheckValuesValidation()).run(ctx)
    await CheckTask(check=next_check).run(ctx)

    assert next_check.executed
    assert len(ctx.contract.errors) == 1
    assert isinstance(ctx.contract.errors[0], AmountNotFoundError)
    assert ctx.contract.errors[0].source == "CheckValuesValidation"
    assert statuses(ctx) == [TaskStatus.RUNNING, TaskStatus.SUCCESS] * 2
    assert len(ctx.contract_repo.saved) == 2


async def test_skipped_check_allows_next_task() -> None:
    ctx = make_context(input_count=0)
    next_check = OptionalCheck()

    await CheckTask(check=RecordingCheck()).run(ctx)
    await CheckTask(check=next_check).run(ctx)

    assert next_check.executed
    assert statuses(ctx) == [
        TaskStatus.RUNNING,
        TaskStatus.SKIPPED,
        TaskStatus.RUNNING,
        TaskStatus.SUCCESS,
    ]


async def test_cancellation_propagates_to_caller() -> None:
    ctx = make_context()

    with pytest.raises(CancelledError):
        await CheckTask(check=RecordingCheck(failure=CancelledError())).run(ctx)

    assert statuses(ctx) == [TaskStatus.RUNNING]
    assert ctx.contract_repo.saved == []


class NoOpTask(BaseTask[TaskRuntime]):
    async def _run(self, ctx: TaskRuntime) -> None:
        pass


async def test_shared_task_lifecycle_preserves_custom_label() -> None:
    ctx = MemoryContext()

    await NoOpTask(label="example").run(ctx)

    assert statuses(ctx) == [TaskStatus.RUNNING, TaskStatus.SUCCESS]
    assert all(record.name == "NoOpTask" for record in ctx.records)
    assert all(record.label == "example" for record in ctx.records)


def test_record_has_aware_utc_timestamp_and_is_immutable() -> None:
    record = TaskRecord(name="CheckTask", status=TaskStatus.RUNNING)

    assert record.timestamp.tzinfo is UTC
    with pytest.raises(FrozenInstanceError):
        record.status = TaskStatus.SUCCESS  # type: ignore[misc]


def test_memory_context_satisfies_public_context_protocol() -> None:
    ctx: CheckTaskContext = MemoryContext()

    assert isinstance(ctx.contract.id, UUID)
