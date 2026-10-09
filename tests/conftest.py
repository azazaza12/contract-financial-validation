from dataclasses import dataclass, field
from uuid import UUID, uuid4

from contract_validation.checks.base import BaseCheck
from contract_validation.entities import CheckExecutionResult, FieldCollector


@dataclass(frozen=True)
class StubDocument:
    """Minimal stand-in for a source document.

    The checks only need a stable identifier to attach field sources to, so the
    full document entity from the original application is not required here.
    """

    file_name: str = "document.pdf"
    id: UUID = field(default_factory=uuid4)


async def run_check(check: BaseCheck, fields: FieldCollector) -> CheckExecutionResult:
    """Resolve declared dependencies and execute a check.

    Replaces the application pipeline task used in the original project, so the
    checks can be exercised without a repository, broker or database.
    """
    check.prepare(fields)
    return await check.execute()
