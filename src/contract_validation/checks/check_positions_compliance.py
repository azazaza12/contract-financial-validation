from typing import cast

from app.domain.entities.errors.checks import BaseCheckError, PositionsComplianceError
from app.domain.entities.single_supplier_fields import (
    DocumentObjectField,
    Specification,
    SpecPositionsField,
)
from app.domain.entities.validation import CheckExecutionResult
from app.domain.ports.checker import IPositionsCompliancer, NumberedPosition

from .base import BaseCheck
from .deps import Requires
from .errors import InsufficientCheckDataError


def _numbered_non_empty_positions(
    spec_positions: Specification,
) -> list[NumberedPosition]:
    positions: list[NumberedPosition] = []
    for number, position in enumerate(spec_positions, 1):
        if position.name is None:
            continue
        stripped = position.name.strip()
        if stripped:
            positions.append(NumberedPosition(number=number, name=stripped))
    return positions


class CheckPositionsCompliance(BaseCheck):
    document_object_field = Requires(DocumentObjectField)
    spec_positions_field = Requires(SpecPositionsField)

    def __init__(self, position_compliancer: IPositionsCompliancer) -> None:
        self.position_compliancer = position_compliancer

    async def execute(self) -> CheckExecutionResult:
        document_object_field = cast("DocumentObjectField", self.document_object_field)
        spec_positions_field = cast("SpecPositionsField", self.spec_positions_field)
        errors: list[BaseCheckError] = []
        label = self.__class__.__name__
        document_object = document_object_field.value.strip()
        positions = _numbered_non_empty_positions(spec_positions_field.value)
        if not positions:
            raise InsufficientCheckDataError(
                label,
                "no position names for compliance check",
            )

        result = await self.position_compliancer.evaluate(
            document_object,
            positions,
        )

        if result.success:
            return self._result(errors)

        errors.append(PositionsComplianceError(message=result.text or ""))
        return self._result(errors)
