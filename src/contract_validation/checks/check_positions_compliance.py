from app.domain.checks.base import BaseCheck
from app.domain.entities.errors import BaseCheckError, PositionsComplianceError
from app.domain.entities.single_supplier_fields import (
    DocumentObjectField,
    SpecPositionsField,
)
from app.domain.entities.validation import CheckExecutionResult
from app.domain.service.checker import IPositionsComplianceService


class CheckPositionsCompliance(BaseCheck):
    async def execute(
        self,
        document_object_field: DocumentObjectField,
        spec_positions_field: SpecPositionsField,
        check_position_compliance_service: IPositionsComplianceService,
    ) -> CheckExecutionResult:

        errors: list[BaseCheckError] = []
        document_object = document_object_field.value
        spec_positions = spec_positions_field.value
        position_names = [position.name for position in spec_positions]
        result = await check_position_compliance_service.evaluate(
            document_object,
            position_names,
        )

        if result.success:
            return self._result(errors)

        errors.append(PositionsComplianceError(message=result.text or ""))
        return self._result(errors)
