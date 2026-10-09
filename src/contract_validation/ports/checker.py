from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from contract_validation.entities.contract_fields import Money


@dataclass
class TranscriptionCheckIssue:
    value: Decimal
    transcription: str
    expected_transcription: str


class ITranscriptionCompliancer(ABC):
    @abstractmethod
    async def evaluate(self, amount: Money) -> TranscriptionCheckIssue | None: ...
