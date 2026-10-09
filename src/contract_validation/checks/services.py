from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from contract_validation.ports.checker import ITranscriptionCompliancer


@dataclass(frozen=True, slots=True)
class CheckServices:
    transcription_compliancer: ITranscriptionCompliancer
