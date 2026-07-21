from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from .errors.checks import BaseCheckError


class CheckStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    PROGRESS = "progress"
    PENDING = "pending"


@dataclass(kw_only=True)
class CheckExecutionResult:
    label: str
    errors: Sequence[BaseCheckError]
    status: CheckStatus
