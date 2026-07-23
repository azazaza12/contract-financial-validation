from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from app.domain.entities.single_supplier_fields import Money


@dataclass
class EvaluateResult:
    text: str | None = None
    success: bool = False
    error: str | None = None


@dataclass(frozen=True)
class NumberedPosition:
    number: int
    name: str


class IPositionsCompliancer(ABC):
    @abstractmethod
    async def evaluate(
        self,
        document_object: str,
        positions: list[NumberedPosition],
    ) -> EvaluateResult: ...


@dataclass
class TranscriptionCheckIssue:
    value: Decimal
    transcription: str
    expected_transcription: str


class ITranscriptionCompliancer(ABC):
    @abstractmethod
    async def evaluate(self, amount: Money) -> TranscriptionCheckIssue | None: ...
