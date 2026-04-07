from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class Source:
    document_id: UUID


@dataclass(frozen=True)
class ValueCandidate:
    value: Any
    sources: list[Source]
