from dataclasses import dataclass
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from app.domain.entities.document import BaseDocument


@dataclass(frozen=True)
class Source:
    document: BaseDocument


@dataclass(frozen=True)
class ValueCandidate:
    value: Any
    sources: list[Source]
