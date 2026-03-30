import logging

from app.domain.checks.base import BaseCheck
from app.domain.entities.single_supplier import DocumentObjectField, SpecPositionsField
from app.domain.entities.validation import BaseResultChecker, CheckExecutionResult
from app.domain.entities.validation_errors import (
    PositionsComplianceErrorCheckResult,
)
from app.domain.pipeline.task import Context


logger = logging.getLogger(__name__)


class CheckPositionsCompliance(BaseCheck):
    def __init__(self, ctx: Context):
        super().__init__()
        self.ctx = ctx

    async def execute(
        self,
        document_object_field: DocumentObjectField,
        spec_positions_field: SpecPositionsField,
    ) -> CheckExecutionResult:

        errors: list[BaseResultChecker] = []
        document_object = document_object_field.value
        spec_positions = spec_positions_field.value
        position_names = [position.name for position in spec_positions]
        result = await self.ctx.check_position_compliance_service.evaluate(
            document_object, position_names
        )

        if result.success:
            logger.info(
                "Document object - [%s]\nAll items correspond "
                "to the subject of the purchase",
                document_object,
            )
            return self._result(errors)

        logger.info(
            "Document object - [%s]\nInappropriate items found:\n [%s]",
            document_object,
            result.text,
        )
        errors.append(PositionsComplianceErrorCheckResult(message=result.text))
        return self._result(errors)
