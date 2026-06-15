from typing import cast

from app.domain.entities.errors.checks import NumberTranscriptionError
from app.domain.entities.single_supplier_fields import (
    AdvancePaymentsField,
    Amount,
    Payment,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult

from .base import BaseCheck
from .deps import CheckServices, OptionalDep
from .errors import InsufficientCheckDataError


class CheckNumberTranscriptionRub(BaseCheck):
    total_amount_field = OptionalDep(TotalAmountField)
    advance_payments_field = OptionalDep(AdvancePaymentsField)

    @staticmethod
    def _amounts_with_transcription(amounts: list[Amount]) -> list[Amount]:
        return [
            amount
            for amount in amounts
            if amount.value is not None
            and amount.transcription is not None
            and amount.transcription.strip()
        ]

    @staticmethod
    def _amounts_from_payment(payment: Payment) -> list[Amount]:
        out: list[Amount] = []
        if payment.amount is not None and payment.amount.value is not None:
            out.append(payment.amount)
        if payment.vat.amount is not None and payment.vat.amount.value is not None:
            out.append(payment.vat.amount)
        return out

    def _extract_amounts_from_fields(
        self,
        fields: list[TotalAmountField | AdvancePaymentsField],
    ) -> list[Amount]:
        amounts: list[Amount] = []
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

    async def execute(self, check_services: CheckServices) -> CheckExecutionResult:
        total_amount_field = cast(
            "TotalAmountField | None",
            self.total_amount_field,
        )
        advance_payments_field = cast(
            "AdvancePaymentsField | None",
            self.advance_payments_field,
        )
        extracted_amounts = self._extract_amounts_from_fields(
            [f for f in (total_amount_field, advance_payments_field) if f is not None],
        )
        checkable_amounts = self._amounts_with_transcription(extracted_amounts)
        if not checkable_amounts:
            raise InsufficientCheckDataError(
                self.__class__.__name__,
                "no amount-transcription pairs to validate",
            )
        result = await check_services.check_transcription_compliance_service.evaluate(
            checkable_amounts,
        )

        errors = [
            NumberTranscriptionError(
                index=issue.index,
                value=issue.value,
                transcription=issue.transcription,
                expected_transcription=issue.expected_transcription,
            )
            for issue in result.issues
        ]
        return self._result(errors)
