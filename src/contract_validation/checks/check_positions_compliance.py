from typing import cast

from app.domain.checks.base import BaseCheck
from app.domain.entities.errors import BaseCheckError, PositionsComplianceError
from app.domain.entities.single_supplier_fields import (
    DocumentObjectField,
    SpecPosition,
    SpecPositionsField,
)
from app.domain.entities.validation import CheckExecutionResult

from .deps import CheckServices, Requires
from .errors import InsufficientCheckDataError


def _non_empty_position_names(spec_positions: list[SpecPosition]) -> list[str]:
    names: list[str] = []
    for position in spec_positions:
        if position.name is None:
            continue
        stripped = position.name.strip()
        if stripped:
            names.append(stripped)
    return names


class CheckPositionsCompliance(BaseCheck):
    document_object_field = Requires(DocumentObjectField)
    spec_positions_field = Requires(SpecPositionsField)

    async def execute(self, check_services: CheckServices) -> CheckExecutionResult:
        document_object_field = cast(
            "DocumentObjectField",
            self.document_object_field,
        )
        spec_positions_field = cast(
            "SpecPositionsField",
            self.spec_positions_field,
        )
        errors: list[BaseCheckError] = []
        label = self.__class__.__name__
        document_object = document_object_field.value.strip()
        position_names = _non_empty_position_names(spec_positions_field.value)
        if not position_names:
            raise InsufficientCheckDataError(
                label,
                "no position names for compliance check",
            )

        result = await check_services.check_position_compliance_service.evaluate(
            document_object,
            position_names,
        )

        if result.success:
            return self._result(errors)

        errors.append(PositionsComplianceError(message=result.text or ""))
        return self._result(errors)
