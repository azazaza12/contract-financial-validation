from app.domain.checks.base import BaseCheck
from app.domain.entities.errors import NumberTranscriptionError
from app.domain.entities.single_supplier_fields import (
    AdvancePaymentsField,
    Amount,
    Payment,
    TotalAmountField,
)
from app.domain.entities.validation import CheckExecutionResult
from app.domain.service.checker import ITranscriptionComplianceService



class CheckNumberTranscriptionRub(BaseCheck):
    @staticmethod
    def _amounts_from_payment(payment: Payment) -> list[Amount]:
        out: list[Amount] = []
        if payment.amount is not None:
            out.append(payment.amount)
        if payment.vat.amount is not None:
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
                if total_amount.taxes is None:
                    continue
                for tax_payment in total_amount.taxes:
                    amounts.extend(self._amounts_from_payment(tax_payment))
                continue

            for advance_payment in field.value:
                if advance_payment.total is not None:
                    amounts.extend(self._amounts_from_payment(advance_payment.total))
                if advance_payment.payments is None:
                    continue
                for payment in advance_payment.payments:
                    amounts.extend(self._amounts_from_payment(payment))
        return amounts

    async def execute(
        self,
        total_amount_field: TotalAmountField | None,
        advance_payments_field: AdvancePaymentsField | None,
        check_transcription_compliance_service: ITranscriptionComplianceService,
    ) -> CheckExecutionResult:
        extracted_amounts = self._extract_amounts_from_fields(
            [f for f in (total_amount_field, advance_payments_field) if f is not None],
        )
        result = await check_transcription_compliance_service.evaluate(
            extracted_amounts,
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
