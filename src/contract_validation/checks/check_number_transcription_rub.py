from typing import cast

from app.domain.entities.errors.checks import NumberTranscriptionError
from app.domain.entities.single_supplier_fields import (
    AdvancePaymentsField,
    Money,
    Payment,
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

    @staticmethod
    def _amounts_from_payment(payment: Payment) -> list[Money]:
        out: list[Money] = []
        if payment.amount is not None and payment.amount.value is not None:
            out.append(payment.amount)
        if payment.vat.amount is not None and payment.vat.amount.value is not None:
            out.append(payment.vat.amount)
        return out

    def _extract_amounts_from_fields(
        self,
        fields: list[TotalAmountField | AdvancePaymentsField],
    ) -> list[Money]:
        amounts: list[Money] = []
        for field in fields:
            if isinstance(field, TotalAmountField):
                total_amount = field.value
                amounts.extend(self._amounts_from_payment(total_amount.total))
                for tax_payment in total_amount.taxes:
                    amounts.extend(self._amounts_from_payment(tax_payment))
                continue

            for advance_payment in field.value:
                if advance_payment.total is not None:
                    amounts.extend(self._amounts_from_payment(advance_payment.total))
                for payment in advance_payment.payments:
                    amounts.extend(self._amounts_from_payment(payment))
        return amounts

    async def execute(self) -> CheckExecutionResult:
        total_amount_fields = cast(
            "list[TotalAmountField]",
            self.total_amount_fields,
        )
        advance_payments_fields = cast(
            "list[AdvancePaymentsField]",
            self.advance_payments_fields,
        )
        extracted_amounts = self._extract_amounts_from_fields(
            [*total_amount_fields, *advance_payments_fields],
        )
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
