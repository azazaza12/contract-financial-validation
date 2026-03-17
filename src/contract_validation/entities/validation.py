from enum import Enum
from pydantic import SerializeAsAny
from typing import Annotated
from dataclasses import dataclass

from app.domain.entities.validation_errors import BaseResultChecker



class CheckStatus(Enum):
    success = "SUCCESS"
    failed = "FAILED"
    progress = "PROGRESS"
    pending = "PENDING"


@dataclass(kw_only=True)
class CheckExecutionResult:
    check_name: str
    result: list[BaseResultChecker]
    status: CheckStatus

