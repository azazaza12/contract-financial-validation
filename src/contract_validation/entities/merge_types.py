from dataclasses import dataclass
from typing import Any

from app.domain.entities import BaseDocument


@dataclass(frozen=True)
class ValueCandidate:
    value: Any
    document: BaseDocument
