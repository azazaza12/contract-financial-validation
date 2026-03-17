from dataclasses import dataclass
from typing import Any

from app.domain.entities.document import BaseDocument


@dataclass(frozen=True)
class Source:
    document: BaseDocument


@dataclass(frozen=True)
class ValueCandidate:
    value: Any
    sources: list[Source]
