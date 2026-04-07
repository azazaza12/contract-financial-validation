from typing import Any

from app.domain.entities.errors.base import BaseContractError
from app.domain.entities.merge_types import ValueCandidate


class BaseMergeError(BaseContractError):
    field_name: str | None = None
    path: str = ""


class ValuesDiscrepancyError(BaseMergeError):
    candidates: list[ValueCandidate]


class ValueNotDefinedError(BaseMergeError):
    value: Any
