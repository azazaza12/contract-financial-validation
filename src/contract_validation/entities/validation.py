from dataclasses import dataclass
from enum import Enum

from app.domain.entities.validation_errors import BaseResultChecker


class CheckStatus(Enum):
    success = "SUCCESS"
    failed = "FAILED"
    progress = "PROGRESS"
    pending = "PENDING"


@dataclass(kw_only=True)
class CheckExecutionResult:
    label: str
    errors: list[BaseResultChecker]
    status: CheckStatus


@dataclass(kw_only=True)
class CheckErrorEntry:
    label: str
    error: BaseResultChecker
    status: CheckStatus
