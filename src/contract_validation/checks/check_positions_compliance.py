from typing import cast

from app.domain.checks.base import BaseCheck
from app.domain.entities.errors import BaseCheckError, PositionsComplianceError
from app.domain.entities.single_supplier_fields import (
    DocumentObjectField,
    SpecPositionsField,
)
from app.domain.entities.validation import CheckExecutionResult

from .deps import CheckServices, Requires


class CheckPositionsCompliance(BaseCheck):
    document_object_field = Requires(DocumentObjectField)
    spec_positions_field = Requires(SpecPositionsField)

    async def execute(self, check_services: CheckServices) -> CheckExecutionResult:
        self.document_object_field = cast(
            "DocumentObjectField",
            self.document_object_field,
        )
        self.spec_positions_field = cast(
            "SpecPositionsField",
            self.spec_positions_field,
        )
        errors: list[BaseCheckError] = []
        document_object = self.document_object_field.value
        spec_positions = self.spec_positions_field.value
        position_names = [position.name for position in spec_positions]
        result = await check_services.check_position_compliance_service.evaluate(
            document_object,
            position_names,
        )

        if result.success:
            return self._result(errors)

        errors.append(PositionsComplianceError(message=result.text or ""))
        return self._result(errors)
