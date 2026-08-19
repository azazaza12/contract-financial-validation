from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from app.domain.ports.checker import ITranscriptionCompliancer


@dataclass(frozen=True, slots=True)
class CheckServices:
    transcription_compliancer: ITranscriptionCompliancer
