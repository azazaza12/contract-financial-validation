from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from contract_validation.entities.errors.base import BaseContractError


class ICheckErrorRepository(Protocol):
    """Only the error persistence operation used by CheckTask."""

    async def save_errors(
        self,
        contract_id: UUID,
        errors: Sequence[BaseContractError],
        kind: str,
    ) -> None: ...
