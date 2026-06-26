from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID


class SourceHeader(StrEnum):
    BODY = "body"
    IN_SPEC = "in_spec"
    AFTER_SPEC = "after_spec"


@dataclass(frozen=True)
class Source:
    document_id: UUID
    headers: tuple[SourceHeader, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ValueCandidate:
    value: Any
    sources: list[Source]
