"""Run a real financial check with in-memory task records and error persistence.

Run after installing the package: python examples/run_check_task.py
The missing total amount is intentional: a business discrepancy does not mean
that task execution failed.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from contract_validation.checks.check_values_validation import CheckValuesValidation
from contract_validation.entities import FieldCollector
from contract_validation.entities.errors.base import BaseContractError
from contract_validation.tasks import CheckTask, TaskRecord


@dataclass
class Contract:
    id: UUID = field(default_factory=uuid4)
    fields: FieldCollector = field(default_factory=lambda: FieldCollector([]))
    errors: list[BaseContractError] = field(default_factory=list)


@dataclass
class MemoryErrorRepository:
    saved: list[tuple[UUID, list[BaseContractError], str]] = field(default_factory=list)

    async def save_errors(
        self, contract_id: UUID, errors: Sequence[BaseContractError], kind: str
    ) -> None:
        self.saved.append((contract_id, list(errors), kind))


@dataclass
class Context:
    contract: Contract = field(default_factory=Contract)
    contract_repo: MemoryErrorRepository = field(default_factory=MemoryErrorRepository)
    records: list[TaskRecord] = field(default_factory=list)

    async def add_record(self, record: TaskRecord) -> None:
        self.records.append(record)


async def main() -> None:
    ctx = Context()
    await CheckTask(check=CheckValuesValidation()).run(ctx)

    for record in ctx.records:
        print(f"Task {record.label}: {record.status}")
    for error in ctx.contract.errors:
        print(f"Discrepancy: {error.error_type}, source={error.source}")
    saved_count = sum(len(errors) for _, errors, _ in ctx.contract_repo.saved)
    print(f"Saved errors: {saved_count}")


if __name__ == "__main__":
    asyncio.run(main())
