from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from app.domain.entities.single_supplier_fields import Amount


@dataclass
class EvaluateResult:
    text: str | None = None
    success: bool = False
    error: str | None = None


class IPositionsCompliancer(ABC):
    @abstractmethod
    async def evaluate(
        self,
        document_object: str,
        position_names: list[str],
    ) -> EvaluateResult: ...


@dataclass
class TranscriptionCheckIssue:
    index: int
    value: Decimal
    transcription: str
    expected_transcription: str


@dataclass
class TranscriptionCheckResult:
    issues: list[TranscriptionCheckIssue]


class ITranscriptionCompliancer(ABC):
    @abstractmethod
    async def evaluate(self, amounts: list[Amount]) -> TranscriptionCheckResult: ...
