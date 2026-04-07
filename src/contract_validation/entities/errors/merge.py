from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import TypeAdapter

from app.domain.entities.errors.base import BaseContractError
from app.domain.entities.merge_types import ValueCandidate


@dataclass
class BaseMergeError(BaseContractError):
    kind: ClassVar[str] = "merge"
    field_name: str | None = None
    path: str = ""


@dataclass
class ValuesDiscrepancyError(BaseMergeError):
    candidates: list[ValueCandidate] = field(default_factory=list)


@dataclass
class ValueNotDefinedError(BaseMergeError):
    value: Any = None


# TODO: create dynamically
_MERGE_ERROR_BY_TYPE: dict[str, type[BaseMergeError]] = {
    "ValuesDiscrepancyError": ValuesDiscrepancyError,
    "ValueNotDefinedError": ValueNotDefinedError,
}


def merge_error_from_dict(data: dict) -> BaseMergeError:
    error_type = data.get("error_type")
    if error_type not in _MERGE_ERROR_BY_TYPE:
        msg = f"Unknown merge error type: {error_type!r}"
        raise ValueError(msg)
    cls = _MERGE_ERROR_BY_TYPE[error_type]
    return TypeAdapter(cls).validate_python(data)
