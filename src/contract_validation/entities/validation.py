from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from .errors.checks import BaseCheckError


class CheckStatus(StrEnum):
    success = "SUCCESS"
    failed = "FAILED"
    progress = "PROGRESS"
    pending = "PENDING"


@dataclass(kw_only=True)
class CheckExecutionResult:
    label: str
    errors: Sequence[BaseCheckError]
    status: CheckStatus
