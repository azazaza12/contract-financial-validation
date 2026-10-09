from typing import cast

from contract_validation.entities.contract_fields import (
    AdvancePaymentsField,
    LocatedAmount,
    TotalAmountField,
)
from contract_validation.entities.errors.checks import NumberTranscriptionError
from contract_validation.entities.validation import CheckExecutionResult
from contract_validation.ports.checker import ITranscriptionCompliancer

from .base import BaseCheck
from .deps import OptionalDep
from .errors import InsufficientCheckDataError


class CheckNumberTranscriptionRub(BaseCheck):
    total_amount_fields = OptionalDep(list[TotalAmountField])
    advance_payments_fields = OptionalDep(list[AdvancePaymentsField])

    def __init__(self, transcription_compliancer: ITranscriptionCompliancer) -> None:
        self.transcription_compliancer = transcription_compliancer

    @staticmethod
    def _amounts_with_transcription(
        amounts: list[LocatedAmount],
    ) -> list[LocatedAmount]:
        return [
            amount
            for amount in amounts
            if amount.money.transcription is not None
            and amount.money.transcription.strip()
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
        extracted_amounts = [
            amount for field in fields for amount in field.located_amounts()
        ]
        checkable_amounts = self._amounts_with_transcription(extracted_amounts)
        if not checkable_amounts:
            raise InsufficientCheckDataError(
                self.__class__.__name__,
                "no amount-transcription pairs to validate",
            )

        errors: list[NumberTranscriptionError] = []
        for index, located_amount in enumerate(checkable_amounts):
            issue = await self.transcription_compliancer.evaluate(
                located_amount.money,
            )
            if issue is None:
                continue
            errors.append(
                NumberTranscriptionError(
                    index=index,
                    value=issue.value,
                    transcription=issue.transcription,
                    expected_transcription=issue.expected_transcription,
                    location=located_amount.location,
                )
            )
        return self._result(errors)
