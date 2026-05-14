from dataclasses import dataclass
from enum import StrEnum

from app.domain.entities.errors import BaseCheckError


class CheckStatus(StrEnum):
    success = "SUCCESS"
    failed = "FAILED"
    progress = "PROGRESS"
    pending = "PENDING"


@dataclass(kw_only=True)
class CheckExecutionResult:
    label: str
    errors: list[BaseCheckError]
    status: CheckStatus
