from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from app.domain.ports.checker import (
        IPositionsCompliancer,
        ITranscriptionCompliancer,
    )


@dataclass(frozen=True, slots=True)
class CheckServices:
    positions_compliancer: IPositionsCompliancer
    transcription_compliancer: ITranscriptionCompliancer
