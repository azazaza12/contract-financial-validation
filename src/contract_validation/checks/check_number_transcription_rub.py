from typing import cast

from app.domain.entities.errors.checks import NumberTranscriptionError
from app.domain.entities.single_supplier_fields import (
    AdvancePaymentsField,
    Money,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult
from app.domain.ports.checker import ITranscriptionCompliancer

from .base import BaseCheck
from .deps import OptionalDep
from .errors import InsufficientCheckDataError


class CheckNumberTranscriptionRub(BaseCheck):
    total_amount_fields = OptionalDep(list[TotalAmountField])
    advance_payments_fields = OptionalDep(list[AdvancePaymentsField])

    def __init__(self, transcription_compliancer: ITranscriptionCompliancer) -> None:
        self.transcription_compliancer = transcription_compliancer

    @staticmethod
    def _amounts_with_transcription(amounts: list[Money]) -> list[Money]:
        return [
            amount
            for amount in amounts
            if amount.value is not None
            and amount.transcription is not None
            and amount.transcription.strip()
        ]

    async def execute(self) -> CheckExecutionResult:
        total_amount_fields = cast(
            "list[TotalAmountField]",
            self.total_amount_fields,
        )
        advance_payments_fields = cast(
            "list[AdvancePaymentsField]",
            self.advance_payments_fields,
        )
        fields: list[TotalAmountField | AdvancePaymentsField] = [
            *total_amount_fields,
            *advance_payments_fields,
        ]
        extracted_amounts: list[Money] = []
        for field in fields:
            extracted_amounts.extend(field.moneys())
        checkable_amounts = self._amounts_with_transcription(extracted_amounts)
        if not checkable_amounts:
            raise InsufficientCheckDataError(
                self.__class__.__name__,
                "no amount-transcription pairs to validate",
            )

        errors: list[NumberTranscriptionError] = []
        for index, amount in enumerate(checkable_amounts):
            issue = await self.transcription_compliancer.evaluate(
                amount,
            )
            if issue is None:
                continue
            errors.append(
                NumberTranscriptionError(
                    index=index,
                    value=issue.value,
                    transcription=issue.transcription,
                    expected_transcription=issue.expected_transcription,
                )
            )
        return self._result(errors)
