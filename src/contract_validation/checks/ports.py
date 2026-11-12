from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from contract_validation.ports.checker import ITranscriptionCompliancer


@dataclass(frozen=True, slots=True)
class CheckPorts:
    """Port implementations supplied when constructing checks."""

    transcription_compliancer: ITranscriptionCompliancer
